import 'dart:convert';
import 'dart:math';
import 'package:cryptography/cryptography.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

/// Encrypted, account-scoped cache. AES-256-GCM authenticates every persisted
/// snapshot. An account's encryption key never goes into SharedPreferences.
/// The web backend depends on the browser's security and is not a substitute
/// for a locked device or a trusted browser profile.
class OfflineStore {
  final FlutterSecureStorage secure;
  final Future<SharedPreferences> Function() preferences;
  final AesGcm cipher = AesGcm.with256bits();
  String? userId;
  Map<String, dynamic> _state = {'responses': <String, dynamic>{}, 'pending': <dynamic>[]};
  OfflineStore({FlutterSecureStorage? secureStorage, Future<SharedPreferences> Function()? prefs})
      : secure = secureStorage ?? const FlutterSecureStorage(),
        preferences = prefs ?? SharedPreferences.getInstance;

  String _key(String uid) => 'cc_offline_key_$uid';
  String _blob(String uid) => 'cc_offline_cache_$uid';
  Future<SecretKey> _secret(String uid) async {
    var encoded = await secure.read(key: _key(uid));
    if (encoded == null) {
      final random = Random.secure();
      encoded = base64Encode(List<int>.generate(32, (_) => random.nextInt(256)));
      await secure.write(key: _key(uid), value: encoded);
    }
    return SecretKey(base64Decode(encoded));
  }

  Future<void> open(String uid) async {
    if (userId == uid) return;
    userId = uid;
    _state = {'responses': <String, dynamic>{}, 'pending': <dynamic>[]};
    final prefs = await preferences();
    final raw = prefs.getString(_blob(uid));
    if (raw == null) return;
    try {
      final envelope = jsonDecode(raw) as Map<String, dynamic>;
      final box = SecretBox(base64Decode(envelope['ciphertext'] as String),
        nonce: base64Decode(envelope['nonce'] as String),
        mac: Mac(base64Decode(envelope['mac'] as String)));
      final plain = await cipher.decrypt(box, secretKey: await _secret(uid));
      final decoded = jsonDecode(utf8.decode(plain));
      if (decoded is Map && decoded['responses'] is Map && decoded['pending'] is List) {
        _state = Map<String, dynamic>.from(decoded);
      }
    } catch (_) {
      // Never expose corrupt or undecryptable data; do not silently erase it.
      _state = {'responses': <String, dynamic>{}, 'pending': <dynamic>[]};
      throw StateError('Offline cache could not be decrypted. Sign out and sign back in to reset it.');
    }
  }

  Future<void> _save() async {
    final uid = userId;
    if (uid == null) return;
    final result = await cipher.encrypt(utf8.encode(jsonEncode(_state)), secretKey: await _secret(uid));
    final payload = jsonEncode({
      'ciphertext': base64Encode(result.cipherText),
      'nonce': base64Encode(result.nonce),
      'mac': base64Encode(result.mac.bytes),
    });
    final prefs = await preferences();
    await prefs.setString(_blob(uid), payload);
  }

  dynamic cached(String key) => (_state['responses'] as Map)[key];
  Future<void> put(String key, dynamic value) async {
    if (userId == null) return;
    final responses = _state['responses'] as Map;
    responses.remove(key); // keep recently refreshed pages in the bounded cache
    responses[key] = value;
    while (responses.length > 130) { responses.remove(responses.keys.first); }
    await _save();
  }

  List<Map<String, dynamic>> get pending =>
    List<Map<String, dynamic>>.from((_state['pending'] as List).map((e) => Map<String, dynamic>.from(e as Map)));

  /// Local revisions advance optimistically, without treating them as server acknowledgements.
  Future<Map<String, dynamic>> enqueue(String chatId, Map<String, dynamic> fields) async {
    if (fields.isEmpty || fields.keys.any((k) => k != 'title' && k != 'is_archived')) {
      throw ArgumentError('Only title and is_archived can be queued offline');
    }
    if (pending.length >= 100) throw StateError('Offline queue full (100 edits)');
    final list = (cached('/conversations') as List?)?.cast<dynamic>();
    if (list == null) throw StateError('Open your conversations online before editing offline');
    final index = list.indexWhere((e) => e['id'] == chatId);
    if (index < 0) throw StateError('Conversation is not saved for offline use');
    final chat = Map<String, dynamic>.from(list[index] as Map);
    final otherEdits = pending.where((op) => op['conversation_id'] == chatId && op['state'] != 'conflict').toList();
    final nextRevision = otherEdits.isEmpty ? (chat['metadata_revision'] as int? ?? 0)
      : max(chat['metadata_revision'] as int? ?? 0, (otherEdits.last['base_revision'] as int) + 1);
    final operation = <String, dynamic>{
      'operation_id': const Uuid().v4(), 'conversation_id': chatId,
      'base_revision': nextRevision,
      ...fields, 'state': 'pending',
    };
    (_state['pending'] as List).add(operation);
    chat.addAll(fields);
    chat['metadata_revision'] = nextRevision + 1;
    list[index] = chat;
    await _save();
    return operation;
  }

  Future<void> removeOperation(String id, {Map<String, dynamic>? server}) async {
    (_state['pending'] as List).removeWhere((e) => e['operation_id'] == id);
    if (server != null) await updateServerChat(server);
    await _save();
  }

  Future<void> updateServerChat(Map<String, dynamic> server) async {
    final list = (cached('/conversations') as List?)?.cast<dynamic>();
    if (list == null) return;
    final index = list.indexWhere((e) => e['id'] == server['id']);
    if (index < 0) return;
    final chat = Map<String, dynamic>.from(list[index] as Map);
    chat.addAll(server);
    list[index] = chat;
    await _save();
  }

  Future<void> markConflict(String id, Map<String, dynamic> server) async {
    for (final op in _state['pending'] as List) {
      if (op['operation_id'] == id) { op['state'] = 'conflict'; op['server'] = server; }
    }
    await _save();
  }

  Future<void> resolve(String chatId, {required bool keepLocal}) async {
    final relevant = pending.where((e) => e['conversation_id'] == chatId).toList();
    if (relevant.isEmpty) return;
    final conflict = relevant.where((e) => e['state'] == 'conflict').firstOrNull;
    if (conflict == null) return;
    final server = Map<String, dynamic>.from(conflict['server'] as Map);
    (_state['pending'] as List).removeWhere((e) => e['conversation_id'] == chatId);
    await updateServerChat(server);
    if (keepLocal) {
      for (final op in relevant) {
        final edits = <String, dynamic>{
          if (op.containsKey('title')) 'title': op['title'],
          if (op.containsKey('is_archived')) 'is_archived': op['is_archived'],
        };
        await enqueue(chatId, edits); // New UUID and rebased revision.
      }
    }
    await _save();
  }

  /// Apply queued edits on top of freshly fetched server metadata. Prevents
  /// stale reads from making pending work disappear from the UI.
  List<dynamic> overlayConversations(List<dynamic> remote) {
    final result = remote.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    for (final op in pending) {
      final index = result.indexWhere((e) => e['id'] == op['conversation_id']);
      if (index < 0) continue;
      if (op['state'] == 'conflict') continue;
      if (op.containsKey('title')) result[index]['title'] = op['title'];
      if (op.containsKey('is_archived')) result[index]['is_archived'] = op['is_archived'];
      result[index]['metadata_revision'] = (result[index]['metadata_revision'] as int? ?? 0) + 1;
    }
    return result;
  }

  Future<void> clearAccount() async {
    final uid = userId;
    if (uid == null) return;
    final prefs = await preferences();
    await prefs.remove(_blob(uid));
    await secure.delete(key: _key(uid));
    _state = {'responses': <String, dynamic>{}, 'pending': <dynamic>[]};
    userId = null;
  }
}
