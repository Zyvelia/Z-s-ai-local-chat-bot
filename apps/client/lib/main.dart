import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'offline_store.dart';
import 'offline_status_ui.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'media_ui.dart';
import 'voice_audio_ui.dart';
import 'story_ui.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:http_parser/http_parser.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'community_ui.dart';
import 'model_control_ui.dart';
import 'admin_security_ui.dart';
import 'sse_parser.dart';
import 'design_system.dart';
import 'quality_ui.dart';

const apiBase = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8000');
void main() => runApp(const CharacterApp());

class ApiHttpError implements Exception {
  final int status;
  final String message;
  final String body;
  ApiHttpError(this.status, this.message, this.body);
  @override String toString() => message;
}

class Api {
  final http.Client client = http.Client();
  String? token;
  final OfflineStore offline = OfflineStore();
  final FlutterSecureStorage _sessionStorage = const FlutterSecureStorage();
  bool offlineMode = false;
  bool _syncInProgress = false;

  Future<void> restoreSession() async {
    final savedToken = await _sessionStorage.read(key: 'cc_session_token');
    final savedUser = await _sessionStorage.read(key: 'cc_session_user');
    if (savedToken == null || savedUser == null) return;
    token = savedToken;
    try {
      await offline.open(savedUser);
      await request('GET', '/users/me');
    } catch (error) {
      // A revoked/expired session must not unlock cached private data forever.
      // Offline availability only lasts until the signed token's expiry.
      try {
        final parts = savedToken.split('.');
        final jwtBody = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))));
        final expires = (jwtBody['exp'] as num).toInt();
        if (DateTime.now().millisecondsSinceEpoch ~/ 1000 >= expires) {
          await logout();
          return;
        }
      } catch (_) { await logout(); return; }
      if (error is ApiHttpError && (error.status == 401 || error.status == 403)) {
        await logout();
      }
      // Network errors preserve an unexpired offline session.
    }
  }

  Future<void> logout() async {
    await offline.clearAccount();
    await _sessionStorage.delete(key: 'cc_session_token');
    await _sessionStorage.delete(key: 'cc_session_user');
    token = null;
    offlineMode = false;
  }

  bool _isCacheable(String method, String path) => method == 'GET' && (
      path == '/characters' || path == '/characters/mine' || path == '/conversations' ||
      RegExp(r'^/characters/[^/]+$').hasMatch(path) ||
      RegExp(r'^/conversations/[^/]+/messages$').hasMatch(path) ||
      RegExp(r'^/conversations/[^/]+/participants$').hasMatch(path) ||
      path == '/personas');

  Uri url(String path) => Uri.parse('$apiBase/api/v1$path');
  Map<String, String> get headers => {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  Future<dynamic> request(String method, String path, [Map<String, dynamic>? body]) async {
    final req = http.Request(method, url(path));
    req.headers.addAll(headers);
    if (body != null) req.body = jsonEncode(body);
    try {
      final response = await http.Response.fromStream(await client.send(req).timeout(const Duration(seconds: 12)));
      if (response.statusCode >= 400) {
        String detail = 'Request failed (${response.statusCode})';
        try { detail = (jsonDecode(response.body)['detail'] ?? detail).toString(); } catch (_) {}
        throw ApiHttpError(response.statusCode, detail, response.body);
      }
      offlineMode = false;
      if (response.statusCode == 204 || response.body.isEmpty) return null;
      final result = jsonDecode(response.body);
      if (_isCacheable(method, path) && offline.userId != null) {
        if (path == '/conversations') {
          await offline.put(path, result);
          return offline.overlayConversations(List<dynamic>.from(result as List));
        }
        await offline.put(path, result);
      }
      return result;
    } on ApiHttpError {
      rethrow; // Never substitute stale data on authorization or server failures.
    } catch (_) {
      if (_isCacheable(method, path) && offline.userId != null) {
        final stored = offline.cached(path);
        if (stored != null) {
          offlineMode = true;
          if (path == '/conversations') return offline.overlayConversations(List<dynamic>.from(stored as List));
          return stored;
        }
      }
      rethrow;
    }
  }

  Future<void> auth(String email, String password, String displayName, bool register) async {
    final data = await request('POST', register ? '/auth/register' : '/auth/login', {
      'email': email, 'password': password, if (register) 'display_name': displayName,
    });
    token = data['access_token'] as String;
    final user = Map<String, dynamic>.from(await request('GET', '/users/me'));
    final id = user['id'] as String;
    await offline.open(id);
    await _sessionStorage.write(key: 'cc_session_user', value: id);
    await _sessionStorage.write(key: 'cc_session_token', value: token);
  }

  Future<Map<String, dynamic>> voiceStatus() async =>
      Map<String, dynamic>.from(await request('GET', '/voice/status'));
  Future<void> setCharacterVoice(String id, String voice) async =>
      await request('PUT', '/voice/characters/$id/voice', {'voice_id': voice});
  Future<Uint8List> synthesizeMessage(String conversation, String message) async {
    final result = Map<String, dynamic>.from(await request('POST', '/voice/conversations/$conversation/messages/$message/synthesize'));
    final id = result['id'] as String;
    final response = await client.get(url('/voice/clips/$id'), headers: headers);
    if (response.statusCode != 200) throw Exception('Voice playback failed (${response.statusCode})');
    return response.bodyBytes;
  }
  Future<String> transcribeAudio(Uint8List wav) async {
    final req = http.MultipartRequest('POST', url('/voice/transcribe'));
    if (token != null) req.headers['Authorization'] = 'Bearer $token';
    req.files.add(http.MultipartFile.fromBytes('file', wav, filename: 'microphone.wav',
      contentType: MediaType('audio', 'wav')));
    final response = await http.Response.fromStream(await client.send(req));
    if (response.statusCode != 200) throw Exception('Transcription failed (${response.statusCode})');
    return (jsonDecode(response.body)['text'] ?? '').toString();
  }
  Future<List<dynamic>> voiceClips(String chat) async =>
      (await request('GET', '/voice/conversations/$chat/clips')) as List;
  Future<Uint8List> voiceClipBytes(String clip) async {
    final response = await client.get(url('/voice/clips/$clip'), headers: headers);
    if (response.statusCode != 200) throw Exception('Audio download failed (${response.statusCode})');
    return response.bodyBytes;
  }
  Future<void> deleteVoiceClip(String clip) async => await request('DELETE', '/voice/clips/$clip');
  Future<List<dynamic>> mediaList(String scope, String id) async =>
      (await request('GET', '/media?${scope}_id=$id')) as List;
  Future<Uint8List> mediaBytes(String id) async {
    final response = await client.get(url('/media/$id'), headers: headers);
    if (response.statusCode != 200) throw Exception('Could not load image');
    return response.bodyBytes;
  }
  Future<Map<String, dynamic>> uploadMedia(String scope, String id, String purpose, String filename, Uint8List bytes) async {
    final req = http.MultipartRequest('POST', url('/media'));
    if (token != null) req.headers['Authorization'] = 'Bearer $token';
    req.fields['purpose'] = purpose;
    req.fields['${scope}_id'] = id;
    final extension = filename.toLowerCase().split('.').last;
    final type = extension == 'png' ? 'png' : extension == 'webp' ? 'webp' : 'jpeg';
    req.files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename, contentType: MediaType('image', type)));
    final response = await http.Response.fromStream(await client.send(req));
    if (response.statusCode != 201) throw Exception('Upload failed (${response.statusCode}): ${response.body}');
    return Map<String,dynamic>.from(jsonDecode(response.body));
  }
  Future<void> removeMedia(String id) async => await request('DELETE', '/media/$id');
  Future<Map<String, dynamic>> myAccountExport() async =>
      Map<String, dynamic>.from(await request('GET', '/privacy/export'));
  Future<void> deleteMyAccount() async => await request('DELETE', '/privacy/account');
  Future<List<dynamic>> myAppeals() async => (await request('GET', '/appeals/mine')) as List;
  Future<void> submitAppeal(String reason, {String? characterId}) async =>
      await request('POST', '/appeals', {'reason': reason, 'character_id': characterId});
  Future<Map<String, dynamic>> adminPerformance() async =>
      Map<String, dynamic>.from(await request('GET', '/admin/performance'));
  Future<Map<String, dynamic>> adminDashboard() async =>
      Map<String, dynamic>.from(await request('GET', '/admin/dashboard'));
  Future<List<dynamic>> adminUsers() async => (await request('GET', '/admin/users')) as List;
  Future<List<dynamic>> adminReports() async => (await request('GET', '/admin/reports?status=all')) as List;
  Future<List<dynamic>> adminAppeals() async => (await request('GET', '/admin/appeals?status=all')) as List;
  Future<List<dynamic>> adminAudit() async => (await request('GET', '/admin/audit')) as List;
  Future<void> adminRestrict(String id, bool suspend, String reason) async =>
      await request('PUT', '/admin/users/$id/restriction', {'suspend': suspend, 'reason': reason});
  Future<void> adminModerate(String id, String status, String reason) async =>
      await request('PUT', '/admin/characters/$id/moderation', {'status': status, 'reason': reason});
  Future<void> adminReportDecision(String id, String status) async =>
      await request('PUT', '/admin/reports/$id', {'status': status, 'note': ''});
  Future<void> adminAppealDecision(String id, String status, String response) async =>
      await request('PUT', '/admin/appeals/$id', {'status': status, 'response': response});
  Future<List<dynamic>> personas() async => (await request('GET', '/personas')) as List;
  Future<void> addPersona(Map<String, dynamic> data) async => await request('POST', '/personas', data);
  Future<void> editPersona(String id, Map<String, dynamic> data) async => await request('PATCH', '/personas/$id', data);
  Future<void> deletePersona(String id) async => await request('DELETE', '/personas/$id');
  Future<void> selectPersona(String conversationId, String? personaId) async =>
      await request('PUT', '/conversations/$conversationId/persona', {'persona_id': personaId});
  Future<List<dynamic>> groupParticipants(String chatId) async => (await request('GET', '/conversations/$chatId/participants')) as List;
  Future<String> startGroup(List<String> characterIds, String title, String scenario, String? personaId) async =>
      (await request('POST', '/conversations/groups', {'character_ids': characterIds, 'title': title, 'scenario': scenario, 'persona_id': personaId}))['id'] as String;
  Future<List<dynamic>> templates() async => (await request('GET', '/character-templates')) as List;
  Future<Map<String, dynamic>> preview(Map<String, dynamic> character, String message) async =>
      Map<String, dynamic>.from(await request('POST', '/characters/preview', {'character': character, 'message': message}));
  Future<Map<String, dynamic>> exportCharacter(String id) async =>
      Map<String, dynamic>.from(await request('GET', '/characters/$id/export'));
  Future<void> importCharacter(Map<String, dynamic> character) async =>
      await request('POST', '/characters/import', {'character': character});
  Future<Map<String, dynamic>> discover({String query = '', String tag = '', String sort = 'trending', int offset = 0}) async {
    final q = Uri(queryParameters: {'q': query, 'tag': tag, 'sort': sort, 'offset': '$offset', 'limit': '20'}).query;
    return Map<String, dynamic>.from(await request('GET', '/characters/discover?$q'));
  }
  Future<List<dynamic>> favorites() async => (await request('GET', '/favorites')) as List;
  Future<void> setFavorite(String id, bool on) async => await request(on ? 'POST' : 'DELETE', '/favorites/$id');
  Future<List<dynamic>> collections() async => (await request('GET', '/collections')) as List;
  Future<Map<String, dynamic>> addCollection(String title, String description) async =>
      Map<String, dynamic>.from(await request('POST', '/collections', {'title': title, 'description': description}));
  Future<void> deleteCollection(String id) async => await request('DELETE', '/collections/$id');
  Future<List<dynamic>> collectionItems(String id) async => (await request('GET', '/collections/$id/characters')) as List;
  Future<void> addToCollection(String collectionId, String characterId) async => await request('POST', '/collections/$collectionId/characters/$characterId');
  Future<void> removeFromCollection(String collectionId, String characterId) async => await request('DELETE', '/collections/$collectionId/characters/$characterId');
  Future<Map<String, dynamic>> creator(String id) async => Map<String, dynamic>.from(await request('GET', '/creators/$id'));
  Future<Map<String, dynamic>> saveCreator(Map<String, dynamic> data) async => Map<String, dynamic>.from(await request('PUT', '/creators/me', data));
  Future<void> followCreator(String id, bool on) async => await request(on ? 'POST' : 'DELETE', '/creators/$id/follow');
  Future<Map<String, dynamic>> creatorCharacters(String id) async => Map<String, dynamic>.from(await request('GET', '/creators/$id/characters'));
  Future<Map<String, dynamic>> characterCommunity(String id) async => Map<String, dynamic>.from(await request('GET', '/characters/$id/community'));
  Future<void> rateCharacter(String id, int stars) async => await request('PUT', '/characters/$id/rating', {'stars': stars});
  Future<void> reportCharacter(String id, String reason, String details) async => await request('POST', '/characters/$id/reports', {'reason': reason, 'details': details});
  Future<Map<String, dynamic>> localModels() async => Map<String, dynamic>.from(await request('GET', '/ai/models'));
  Future<Map<String, dynamic>> localHealth() async => Map<String, dynamic>.from(await request('GET', '/ai/health'));
  Future<void> setCharacterModel(String id, String? model) async =>
      await request('PUT', '/characters/$id/model', {'model': model});
  Future<void> setChatInference(String id, Map<String, dynamic> data) async =>
      await request('PUT', '/conversations/$id/inference', data);
  Future<List<dynamic>> characters() async => (await request('GET', '/characters')) as List;
  Future<List<dynamic>> mine() async => (await request('GET', '/characters/mine')) as List;
  Future<List<dynamic>> conversations() async => (await request('GET', '/conversations')) as List;
  Future<Map<String, dynamic>> character(String id) async => Map<String, dynamic>.from(await request('GET', '/characters/$id'));
  Future<void> editCharacter(String id, Map<String, dynamic> changes) async => await request('PATCH', '/characters/$id', changes);
  Future<void> editConversation(String id, Map<String, dynamic> changes) async {
    if (changes.isNotEmpty && changes.keys.every((key) => key == 'title' || key == 'is_archived')) {
      await offline.enqueue(id, changes);
      await syncPending(); // Persist locally even when server is unavailable.
    } else {
      await request('PATCH', '/conversations/$id', changes); // Unsafe edits stay online-only.
    }
  }
  Future<void> syncPending() async {
    if (_syncInProgress || token == null || offline.userId == null) return;
    _syncInProgress = true;
    try {
      final blocked = <String>{};
      for (final op in offline.pending) {
        final id = op['conversation_id'] as String;
        if (blocked.contains(id)) continue;
        if (op['state'] == 'conflict') { blocked.add(id); continue; }
        try {
          final payload = <String, dynamic>{
            'operation_id': op['operation_id'], 'base_revision': op['base_revision'],
            if (op.containsKey('title')) 'title': op['title'],
            if (op.containsKey('is_archived')) 'is_archived': op['is_archived'],
          };
          final result = Map<String, dynamic>.from(await request('POST', '/sync/conversations/$id/metadata', payload));
          await offline.removeOperation(op['operation_id'] as String, server: result);
        } on ApiHttpError catch (error) {
          if (error.status == 409) {
            try {
              final body = jsonDecode(error.body) as Map<String, dynamic>;
              final detail = body['detail'] as Map;
              final remote = Map<String, dynamic>.from(detail['server'] as Map);
              await offline.markConflict(op['operation_id'] as String, remote);
            } catch (_) { rethrow; }
            blocked.add(id);
          } else if (error.status == 404) {
            // The chat may have been deleted on another device. Preserve it for review.
            await offline.markConflict(op['operation_id'] as String, {'id': id, 'title': '(Deleted on server)', 'metadata_revision': -1, 'is_archived': false});
            blocked.add(id);
          } else { break; }
        } catch (_) { offlineMode = true; break; }
      }
    } finally { _syncInProgress = false; }
  }
  Future<void> resolveSyncConflict(String chatId, bool keepLocal) async {
    final found = offline.pending.where((o) => o['conversation_id'] == chatId && o['state'] == 'conflict').toList();
    if (found.isEmpty) return;
    final server = found.first['server'] as Map;
    if ((server['metadata_revision'] as int? ?? 0) < 0) {
      await offline.resolve(chatId, keepLocal: false);
      return;
    }
    await offline.resolve(chatId, keepLocal: keepLocal);
    if (keepLocal) await syncPending();
  }
  Future<void> deleteConversation(String id) async => await request('DELETE', '/conversations/$id');
  Future<List<dynamic>> memories(String id) async => (await request('GET', '/conversations/$id/memories')) as List;
  Future<void> addMemory(String id, String content) async => await request('POST', '/conversations/$id/memories', {'content': content});
  Future<void> deleteMemory(String id, String memoryId) async => await request('DELETE', '/conversations/$id/memories/$memoryId');
  Future<List<dynamic>> learnedMemories(String id) async => (await request('GET', '/conversations/$id/learned-memories')) as List;
  Future<void> editLearned(String id, String memoryId, String content) async => await request('PATCH', '/conversations/$id/learned-memories/$memoryId', {'content': content});
  Future<void> deleteLearned(String id, String memoryId) async => await request('DELETE', '/conversations/$id/learned-memories/$memoryId');
  Future<Map<String, dynamic>> summary(String id) async => Map<String, dynamic>.from(await request('GET', '/conversations/$id/summary'));
  Future<void> clearSummary(String id) async => await request('DELETE', '/conversations/$id/summary');
  Future<List<dynamic>> lorebook(String characterId) async => (await request('GET', '/characters/$characterId/lorebook')) as List;
  Future<void> addLore(String characterId, Map<String, dynamic> data) async => await request('POST', '/characters/$characterId/lorebook', data);
  Future<void> editLore(String characterId, String entryId, Map<String, dynamic> data) async => await request('PATCH', '/characters/$characterId/lorebook/$entryId', data);
  Future<void> deleteLore(String characterId, String entryId) async => await request('DELETE', '/characters/$characterId/lorebook/$entryId');
  Future<List<dynamic>> messages(String id) async => (await request('GET', '/conversations/$id/messages')) as List;
  Future<Map<String, dynamic>> promptDiagnostics(String id) async => Map<String, dynamic>.from(await request('GET', '/conversations/$id/prompt-diagnostics')); 
  Future<List<dynamic>> alternatives(String chat, String message) async => (await request('GET', '/conversations/$chat/alternatives/$message')) as List;
  Future<List<dynamic>> selectAlternative(String chat, String message) async => (await request('POST', '/conversations/$chat/alternatives/select', {'assistant_id': message})) as List;
  Future<void> editMessage(String chat, String message, String content) async => await request('PATCH', '/conversations/$chat/messages/$message', {'content': content});
  Future<void> deleteMessage(String chat, String message) async => await request('DELETE', '/conversations/$chat/messages/$message');
  Future<String> branch(String chat, String message) async => (await request('POST', '/conversations/$chat/branch', {'message_id': message}))['id'] as String;
  Future<String> startConversation(String characterId, {int greetingIndex = 0, String? personaId}) async =>
      (await request('POST', '/conversations', {'character_id': characterId, 'greeting_index': greetingIndex, 'persona_id': personaId}))['id'] as String;

  // Parse SSE chunks regardless of HTTP/TCP segment boundaries.
  Stream<Map<String, dynamic>> streamReply(String conversationId, String message, {String? regenerateId, bool retry = false, bool groupTurn = false, String? speakerId}) async* {
    final path = groupTurn ? '/group/turn' : regenerateId != null ? '/messages/regenerate' : retry ? '/messages/retry' : '/messages/stream';
    final req = http.Request('POST', url('/conversations/$conversationId$path'));
    req.headers.addAll(headers);
    req.body = jsonEncode(groupTurn ? {'character_id': speakerId} : regenerateId != null ? {'assistant_id': regenerateId} : retry ? <String, dynamic>{} : {'content': message});
    final response = await client.send(req);
    if (response.statusCode >= 400) {
      final errorResponse = await http.Response.fromStream(response);
      throw Exception('Chat request failed (${response.statusCode}): ${errorResponse.body}');
    }
    // A generation may send token, done, or error events. Keep their
    // boundaries intact even when frames are split across TCP packets.
    yield* decodeChatEvents(response.stream);
  }
}

class CharacterApp extends StatefulWidget {
  const CharacterApp({super.key});
  @override
  State<CharacterApp> createState() => _CharacterAppState();
}

class _CharacterAppState extends State<CharacterApp> {
  final api = Api();
  ThemeMode mode = ThemeMode.system;
  bool restoring = true;
  @override void initState() {
    super.initState();
    api.restoreSession().catchError((_) {}).whenComplete(() {
      if (mounted) setState(() => restoring = false);
    });
  }
  void cycleTheme() => setState(() => mode = mode == ThemeMode.system ? ThemeMode.dark : mode == ThemeMode.dark ? ThemeMode.light : ThemeMode.system);
  @override
  Widget build(BuildContext context) => MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'Character Chat',
        theme: AppThemes.build(Brightness.light),
        darkTheme: AppThemes.build(Brightness.dark),
        themeMode: mode,
        home: restoring ? const Scaffold(body: Center(child: CircularProgressIndicator()))
            : api.token == null
            ? LoginScreen(api: api, onLogin: () => setState(() {}))
            : HomeScreen(api: api, onLogout: () async {
                await api.logout();
                if (mounted) setState(() {});
              }, onTheme: cycleTheme),
      );
}

void showError(BuildContext context, Object error) {
  if (context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.toString())));
  }
}

class LoginScreen extends StatefulWidget {
  final Api api;
  final VoidCallback onLogin;
  const LoginScreen({super.key, required this.api, required this.onLogin});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final email = TextEditingController();
  final password = TextEditingController();
  final name = TextEditingController();
  bool register = false;
  bool busy = false;
  @override
  void dispose() { email.dispose(); password.dispose(); name.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Card(child: Padding(padding: const EdgeInsets.all(24), child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('Character Chat', style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              if (register) TextField(controller: name, decoration: const InputDecoration(labelText: 'Display name')),
              TextField(controller: email, decoration: const InputDecoration(labelText: 'Email')),
              TextField(controller: password, obscureText: true, decoration: const InputDecoration(labelText: 'Password (10+ characters)')),
              const SizedBox(height: 16),
              FilledButton(onPressed: busy ? null : () async {
                setState(() => busy = true);
                try {
                  await widget.api.auth(email.text.trim(), password.text, name.text.trim(), register);
                  widget.onLogin();
                } catch (e) { if (context.mounted) showError(context, e); }
                finally { if (mounted) setState(() => busy = false); }
              }, child: Text(register ? 'Create account' : 'Sign in')),
              TextButton(onPressed: () => setState(() => register = !register),
                  child: Text(register ? 'Already registered? Sign in' : 'Create an account')),
            ],
          ))),
        )),
      );
}

class HomeScreen extends StatefulWidget {
  final Api api;
  final VoidCallback onLogout;
  final VoidCallback? onTheme;
  const HomeScreen({super.key, required this.api, required this.onLogout, this.onTheme});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  List<dynamic> characters = [];
  List<dynamic> mine = [];
  List<dynamic> conversations = [];
  bool busy = true;
  bool openedIncomingLink = false;
  String? loadError;
  Timer? reconnectTimer;
  bool refreshing = false;
  @override void dispose() { reconnectTimer?.cancel(); super.dispose(); }
  int selectedTab = 0;
  @override
  void initState() {
    super.initState();
    refresh();
    reconnectTimer = Timer.periodic(const Duration(seconds: 25), (_) async {
      if (mounted) await refresh(); // refresh server state and retry queue
    });
  }
  Future<void> refresh() async {
    if (refreshing) return;
    refreshing = true;
    try {
      await widget.api.syncPending();
      final values = await Future.wait([widget.api.characters(), widget.api.mine(), widget.api.conversations()]);
      if (mounted) setState(() { characters = values[0]; mine = values[1]; conversations = values[2]; busy = false; loadError = null; });
      final linkedId = Uri.base.queryParameters['character'];
      if (!openedIncomingLink && linkedId != null && linkedId.isNotEmpty && mounted) {
        openedIncomingLink = true;
        WidgetsBinding.instance.addPostFrameCallback((_) async {
          if (!mounted) return;
          try {
            await openProfile({'id': linkedId});
          } catch (e) { if (mounted) showError(context, e); }
        });
      }
    } catch (e) { if (mounted) { setState(() { busy = false; loadError = e.toString(); }); showError(context, e); } }
    finally { refreshing = false; }
  }
  Future<void> start(Map<String, dynamic> character, [int greetingIndex = 0]) async {
    try {
      final id = await widget.api.startConversation(character['id'] as String, greetingIndex: greetingIndex);
      if (!mounted) return;
      await Navigator.push(context, MaterialPageRoute(builder: (_) => ChatScreen(api: widget.api, conversationId: id, characterName: character['name'] as String)));
      await refresh();
    } catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> openProfile(Map<String, dynamic> character) async {
    await Navigator.push(context, MaterialPageRoute(builder: (_) => CharacterProfileScreen(
      api: widget.api, characterId: character['id'] as String,
      onChat: (profile, greetingIndex) async {
        Navigator.pop(context);
        await start(profile, greetingIndex);
      },
    )));
    if (mounted) await refresh();
  }
  Future<void> createGroup() async {
    final id = await Navigator.push<String>(context, MaterialPageRoute(builder: (_) => GroupCreatorScreen(api: widget.api)));
    if (id != null && mounted) {
      await Navigator.push(context, MaterialPageRoute(builder: (_) => ChatScreen(
        api: widget.api, conversationId: id, characterName: 'Group roleplay')));
      if (mounted) await refresh();
    }
  }
  Future<void> openExisting(Map<String, dynamic> chat) async {
    String name = chat['title']?.toString() ?? 'Character';
    try {
      final profile = await widget.api.character(chat['character_id'] as String);
      name = profile['name']?.toString() ?? name;
    } catch (_) { /* Existing chat may outlive access to a private character. */ }
    if (!mounted) return;
    await Navigator.push(context, MaterialPageRoute(builder: (_) => ChatScreen(
      api: widget.api, conversationId: chat['id'] as String, characterName: name,
    )));
    if (mounted) await refresh();
  }
  Future<void> conversationAction(Map<String, dynamic> chat, String action) async {
    final id = chat['id'] as String;
    try {
      if (action == 'rename') {
        final controller = TextEditingController(text: chat['title']?.toString() ?? 'New chat');
        final title = await showDialog<String>(context: context, builder: (context) => AlertDialog(
          title: const Text('Rename conversation'),
          content: TextField(controller: controller, maxLength: 120, autofocus: true),
          actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Save'))],
        ));
        controller.dispose();
        if (title == null || title.isEmpty) return;
        await widget.api.editConversation(id, {'title': title});
      } else if (action == 'archive') {
        await widget.api.editConversation(id, {'is_archived': chat['is_archived'] != true});
      } else if (action == 'delete') {
        final confirm = await showDialog<bool>(context: context, builder: (context) => AlertDialog(
          title: const Text('Delete conversation?'),
          content: const Text('All messages and pinned memories in this chat will be permanently deleted.'),
          actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete'))],
        ));
        if (confirm != true) return;
        await widget.api.deleteConversation(id);
      }
      await refresh();
    } catch (e) { if (mounted) showError(context, e); }
  }

  Future<void> syncNow() async {
    await widget.api.syncPending();
    if (mounted) await refresh();
  }

  Future<void> reviewConflicts() async {
    for (final item in widget.api.offline.pending.where((o) => o['state'] == 'conflict').toList()) {
      if (!mounted) return;
      final remote = Map<String, dynamic>.from(item['server'] as Map);
      final description = remote['metadata_revision'] == -1
          ? 'This conversation was deleted on another device. The queued edit cannot be applied.'
          : 'Server title: ${remote['title']}\nYour queued title: ${item['title'] ?? '(not changed)'}\nServer archived: ${remote['is_archived']}';
      final keepLocal = await showDialog<bool>(context: context, barrierDismissible: false,
        builder: (context) => AlertDialog(title: const Text('Sync conflict'),
          content: Text(description), actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Keep server')),
            if (remote['metadata_revision'] != -1)
              FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Apply my edits')),
          ]));
      if (keepLocal == null) break;
      await widget.api.resolveSyncConflict(item['conversation_id'] as String, keepLocal);
    }
    if (mounted) await refresh();
  }

  Future<void> _openTab(int index) async {
    setState(() => selectedTab = index);
    if (index == 3) {
      await Navigator.push(context, MaterialPageRoute(builder: (_) => PersonaManagerScreen(api: widget.api)));
      if (mounted) setState(() => selectedTab = 0);
    }
  }
  Future<void> _importJson() async {
    final input = TextEditingController();
    try {
      final data = await showDialog<String>(context: context, builder: (ctx) => AlertDialog(
        title: const Text('Import character JSON'),
        content: SizedBox(width: 520, child: TextField(controller: input, maxLines: 10,
          decoration: const InputDecoration(hintText: 'Paste exported character JSON'))),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, input.text), child: const Text('Import'))]));
      if (data == null) return;
      final obj = jsonDecode(data) as Map<String, dynamic>;
      if (obj['format'] != 'character-chat-v1') throw const FormatException('Unsupported character format');
      await widget.api.importCharacter(Map<String, dynamic>.from(obj['character'] as Map));
      await refresh();
    } catch (e) { if (mounted) showError(context, e); }
    finally { input.dispose(); }
  }
  Widget _overview(BuildContext context) => ListView(children: [
    SectionTitle('Explore worlds', subtitle: 'Discover characters and new stories', action:
      TextButton(onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) =>
        DiscoveryScreen(api: widget.api, onOpen: openProfile))), child: const Text('See all'))),
    if (characters.isEmpty) const EmptyView(icon: Icons.auto_awesome_outlined,
      title: 'No public characters', message: 'Create the first character or explore again later.'),
    LayoutBuilder(builder: (context, constraints) => GridView.builder(
      shrinkWrap: true, physics: const NeverScrollableScrollPhysics(),
      gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: AppLayout.gridColumns(constraints.maxWidth), mainAxisSpacing: 8, crossAxisSpacing: 8,
        mainAxisExtent: 175), itemCount: characters.length > 8 ? 8 : characters.length,
      itemBuilder: (_, i) { final c = Map<String, dynamic>.from(characters[i]);
        return CharacterTile(key: ValueKey('discovery-${c['id']}'), character: c, onTap: () => openProfile(c)); })),
    const SizedBox(height: 28),
    SectionTitle('Continue chatting', subtitle: 'Return to your conversations'),
    if (conversations.isEmpty) const EmptyView(icon: Icons.forum_outlined,
      title: 'Your story starts here', message: 'Open a character profile to start a chat.'),
    ...conversations.take(6).map((raw) => _conversationRow(Map<String, dynamic>.from(raw))),
  ]);
  Widget _conversationRow(Map<String, dynamic> c) => Card(child: ListTile(
    leading: CircleAvatar(child: Icon(c['chat_mode'] == 'group' ? Icons.groups_2_outlined : Icons.chat_bubble_outline)),
    title: Text(c['title']?.toString() ?? 'New chat', maxLines: 1, overflow: TextOverflow.ellipsis),
    subtitle: Text(c['is_archived'] == true ? 'Archived' : c['chat_mode'] == 'group' ? 'Group roleplay' : 'Continue conversation'),
    onTap: () => openExisting(c), trailing: PopupMenuButton<String>(tooltip: 'Conversation actions',
      onSelected: (value) => conversationAction(c, value), itemBuilder: (_) => [
        const PopupMenuItem(value: 'rename', child: Text('Rename')),
        PopupMenuItem(value: 'archive', child: Text(c['is_archived'] == true ? 'Unarchive' : 'Archive')),
        const PopupMenuItem(value: 'delete', child: Text('Delete')),
      ])));
  Widget _content(BuildContext context) {
    if (busy) return const LoadingView(label: 'Loading your character world');
    if (loadError != null) return RetryView(message: loadError!, onRetry: refresh);
    switch (selectedTab) {
      case 1:
        return ListView(children: [SectionTitle('Conversations', subtitle: 'Resume, rename or archive your chats',
          action: IconButton(onPressed: createGroup, tooltip: 'Create group chat', icon: const Icon(Icons.group_add_outlined))),
          if (conversations.isEmpty) const EmptyView(icon: Icons.chat_bubble_outline,
            title: 'No conversations', message: 'Choose a character to start your first conversation.'),
          ...conversations.map((c) => _conversationRow(Map<String, dynamic>.from(c)))]);
      case 2:
        return ListView(children: [SectionTitle('My characters', subtitle: 'Manage your creations',
          action: IconButton(onPressed: _importJson, icon: const Icon(Icons.file_upload_outlined), tooltip: 'Import JSON')),
          if (mine.isEmpty) const EmptyView(icon: Icons.person_add_alt_1_outlined,
            title: 'No characters yet', message: 'Create a character to get started.'),
          LayoutBuilder(builder: (context, box) => GridView.builder(
            shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), itemCount: mine.length,
            gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: AppLayout.gridColumns(box.maxWidth), mainAxisExtent: 175,
              crossAxisSpacing: 8, mainAxisSpacing: 8), itemBuilder: (_, i) {
                final c = Map<String, dynamic>.from(mine[i]);
                return CharacterTile(character: c, onTap: () => openProfile(c)); }))]);
      default: return _overview(context);
    }
  }
  Widget _sideNavigation() => NavigationRail(
    selectedIndex: selectedTab.clamp(0, 2), onDestinationSelected: _openTab,
    extended: true, minExtendedWidth: 200,
    leading: Padding(padding: const EdgeInsets.all(16), child: Text('CHARACTER CHAT',
      style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold))),
    destinations: const [NavigationRailDestination(icon: Icon(Icons.explore_outlined), selectedIcon: Icon(Icons.explore), label: Text('Discover')),
      NavigationRailDestination(icon: Icon(Icons.forum_outlined), selectedIcon: Icon(Icons.forum), label: Text('Conversations')),
      NavigationRailDestination(icon: Icon(Icons.auto_stories_outlined), selectedIcon: Icon(Icons.auto_stories), label: Text('My characters'))]);
  @override Widget build(BuildContext context) => LayoutBuilder(builder: (context, viewport) {
    final wide = AppLayout.isWide(viewport.maxWidth);
    return Scaffold(
      appBar: AppBar(title: const Text('Character Chat'), actions: [
        if (widget.api.offlineMode) Tooltip(message: 'Showing encrypted offline cache',
          child: Icon(Icons.cloud_off_outlined, color: Theme.of(context).colorScheme.error)),
        if (widget.api.offline.pending.isNotEmpty)
          TextButton.icon(onPressed: widget.api.offline.pending.any((o) => o['state'] == 'conflict')
              ? reviewConflicts : syncNow,
            icon: Icon(widget.api.offline.pending.any((o) => o['state'] == 'conflict')
              ? Icons.warning_amber_outlined : Icons.sync_outlined),
            label: Text('${widget.api.offline.pending.length} pending')),
        IconButton(tooltip: 'Reconnect and sync', icon: const Icon(Icons.sync), onPressed: syncNow),
        IconButton(icon: const Icon(Icons.search), tooltip: 'Search characters', onPressed: () => Navigator.push(context,
          MaterialPageRoute(builder: (_) => DiscoveryScreen(api: widget.api, onOpen: openProfile)))),
        PopupMenuButton<String>(tooltip: 'More actions', onSelected: (v) async {
          switch (v) {
            case 'favorites': await Navigator.push(context, MaterialPageRoute(builder: (_) => LibraryScreen(api: widget.api, onOpen: openProfile))); break;
            case 'profile': await Navigator.push(context, MaterialPageRoute(builder: (_) => CreatorScreen(api: widget.api, own: true, onOpen: openProfile))); break;
            case 'personas': await Navigator.push(context, MaterialPageRoute(builder: (_) => PersonaManagerScreen(api: widget.api))); break;
            case 'groups': await createGroup(); break;
            case 'models': await Navigator.push(context, MaterialPageRoute(builder: (_) => ModelHealthScreen(api: widget.api))); break;
            case 'privacy': await Navigator.push(context, MaterialPageRoute(builder: (_) => PrivacyScreen(api: widget.api, onDeleted: widget.onLogout))); break;
            case 'admin': await Navigator.push(context, MaterialPageRoute(builder: (_) => AdminScreen(api: widget.api))); break;
            case 'theme': widget.onTheme?.call(); break;
            case 'refresh': await refresh(); break;
            case 'logout': widget.onLogout(); break;
          }
        }, itemBuilder: (_) => const [
          PopupMenuItem(value: 'favorites', child: Text('Favorites & collections')),
          PopupMenuItem(value: 'profile', child: Text('Creator profile')),
          PopupMenuItem(value: 'personas', child: Text('My personas')),
          PopupMenuItem(value: 'groups', child: Text('Create group chat')),
          PopupMenuItem(value: 'models', child: Text('Local AI status')),
          PopupMenuItem(value: 'privacy', child: Text('Privacy & appeals')),
          PopupMenuItem(value: 'admin', child: Text('Administration')),
          PopupMenuItem(value: 'theme', child: Text('Change theme')),
          PopupMenuItem(value: 'refresh', child: Text('Refresh')),
          PopupMenuItem(value: 'logout', child: Text('Log out')),
        ]),
      ]),
      floatingActionButton: FloatingActionButton.extended(tooltip: 'Create character',
        onPressed: () async { await Navigator.push(context, MaterialPageRoute(builder: (_) => CharacterEditorScreen(api: widget.api))); if (mounted) await refresh(); },
        icon: const Icon(Icons.add), label: const Text('Create character')),
      bottomNavigationBar: wide ? null : NavigationBar(selectedIndex: selectedTab.clamp(0, 2), onDestinationSelected: _openTab,
        destinations: const [NavigationDestination(icon: Icon(Icons.explore_outlined), label: 'Discover'),
          NavigationDestination(icon: Icon(Icons.forum_outlined), label: 'Chats'),
          NavigationDestination(icon: Icon(Icons.auto_stories_outlined), label: 'My characters')]),
      body: Column(children: [
        OfflineSyncStatus(offline: widget.api.offlineMode,
          pending: widget.api.offline.pending.length,
          conflicts: widget.api.offline.pending.where((e) => e['state'] == 'conflict').length,
          onSync: syncNow, onReview: reviewConflicts),
        Expanded(child: Row(children: [if (wide) _sideNavigation(),
          Expanded(child: PageFrame(child: _content(context)))])),
      ]),
    );
  });

}

// Full creator editor used for new and existing characters.
class CharacterEditorScreen extends StatefulWidget {
  final Api api;
  final Map<String, dynamic>? existing;
  const CharacterEditorScreen({super.key, required this.api, this.existing});
  @override
  State<CharacterEditorScreen> createState() => _CharacterEditorScreenState();
}
class _CharacterEditorScreenState extends State<CharacterEditorScreen> {
  final name = TextEditingController();
  final tagline = TextEditingController();
  final personality = TextEditingController();
  final scenario = TextEditingController();
  final advanced = TextEditingController();
  final appearance = TextEditingController();
  final accent = TextEditingController(text: "#6750A4");
  String appearanceStyle = "classic";
  final tags = TextEditingController();
  final examples = TextEditingController();
  final previewInput = TextEditingController(text: 'Hello, who are you?');
  final greetings = <TextEditingController>[];
  String templateKey = 'custom';
  List<dynamic> templates = [];
  bool isPublic = false;
  bool busy = false;
  String? previewResult;
  @override
  void initState() {
    super.initState();
    final c = widget.existing;
    if (c != null) {
      name.text = c['name']?.toString() ?? '';
      tagline.text = c['tagline']?.toString() ?? '';
      personality.text = c['personality']?.toString() ?? '';
      scenario.text = c['scenario']?.toString() ?? '';
      advanced.text = c['advanced_definition']?.toString() ?? '';
      appearance.text = c['appearance_description']?.toString() ?? '';
      appearanceStyle = c['appearance_style']?.toString() ?? 'classic';
      accent.text = c['accent_color']?.toString() ?? '#6750A4';
      tags.text = (c['tags'] as List? ?? []).join(', ');
      templateKey = c['template_key']?.toString() ?? 'custom';
      isPublic = c['is_public'] == true;
      examples.text = (c['example_dialogue'] as List? ?? []).map((e) => '${e['role']}: ${e['content']}').join('\n');
      final options = c['greetings'] as List? ?? [];
      for (final g in options.isEmpty ? [c['greeting'] ?? 'Hello!'] : options) {
        greetings.add(TextEditingController(text: g.toString()));
      }
    } else {
      greetings.add(TextEditingController(text: 'Hello!'));
    }
    loadTemplates();
  }
  Future<void> loadTemplates() async {
    try { final result = await widget.api.templates();
      if (mounted) setState(() => templates = result);
    } catch (_) { /* Custom characters remain usable without catalog. */ }
  }
  void applyTemplate(String key) {
    final template = templates.where((t) => t['key'] == key).toList();
    setState(() {
      templateKey = key;
      if (template.isNotEmpty && key != 'custom') {
        personality.text = template.first['personality']?.toString() ?? '';
        scenario.text = template.first['scenario']?.toString() ?? '';
      }
    });
  }
  Map<String, dynamic> payload() {
    final lines = examples.text.split('\n').where((l) => l.trim().isNotEmpty);
    final dialogue = <Map<String, String>>[];
    for (final line in lines) {
      final marker = line.indexOf(':');
      if (marker < 1) throw const FormatException('Example lines must start with user: or assistant:');
      final role = line.substring(0, marker).trim().toLowerCase();
      if (role != 'user' && role != 'assistant') throw const FormatException('Example role must be user or assistant');
      dialogue.add({'role': role, 'content': line.substring(marker + 1).trim()});
    }
    final options = greetings.map((g) => g.text.trim()).toList();
    if (options.isEmpty || options.any((g) => g.isEmpty)) throw const FormatException('Add at least one nonempty greeting');
    return {
      'name': name.text.trim(), 'tagline': tagline.text.trim(),
      'personality': personality.text.trim(), 'scenario': scenario.text.trim(),
      'greeting': options.first, 'greetings': options,
      'template_key': templateKey, 'advanced_definition': advanced.text.trim(),
      'tags': tags.text.split(',').map((t) => t.trim()).where((t) => t.isNotEmpty).toList(),
      'example_dialogue': dialogue, 'is_public': isPublic,
      'appearance_description': appearance.text.trim(),
      'appearance_style': appearanceStyle, 'accent_color': accent.text.trim(),
    };
  }
  Future<void> save() async {
    setState(() => busy = true);
    try {
      final data = payload();
      if (widget.existing == null) {
        await widget.api.request('POST', '/characters', data);
      } else {
        await widget.api.editCharacter(widget.existing!['id'] as String, data);
      }
      if (mounted) Navigator.pop(context, true);
    } catch (e) { if (mounted) showError(context, e); }
    finally { if (mounted) setState(() => busy = false); }
  }
  Future<void> preview() async {
    setState(() { busy = true; previewResult = null; });
    try {
      final result = await widget.api.preview(payload(), previewInput.text.trim());
      if (mounted) setState(() => previewResult = result['reply']?.toString() ?? 'No response');
    } catch (e) { if (mounted) showError(context, e); }
    finally { if (mounted) setState(() => busy = false); }
  }
  @override
  void dispose() {
    for (final c in [name, tagline, personality, scenario, advanced, appearance, accent, tags, examples, previewInput, ...greetings]) { c.dispose(); }
    super.dispose();
  }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.existing == null ? 'Create character' : 'Advanced character editor')),
    body: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 760),
      child: ListView(padding: const EdgeInsets.all(20), children: [
        if (templates.isNotEmpty) DropdownButtonFormField<String>(
          initialValue: templates.any((t) => t['key'] == templateKey) ? templateKey : 'custom',
          decoration: const InputDecoration(labelText: 'Personality template'),
          items: templates.map((t) => DropdownMenuItem<String>(value: t['key'] as String, child: Text(t['name'] as String))).toList(),
          onChanged: (v) { if (v != null) applyTemplate(v); },
        ),
        TextField(controller: name, maxLength: 80, decoration: const InputDecoration(labelText: 'Name')),
        TextField(controller: tagline, maxLength: 200, decoration: const InputDecoration(labelText: 'Tagline')),
        TextField(controller: personality, maxLines: 4, maxLength: 8000, decoration: const InputDecoration(labelText: 'Personality (required)')),
        TextField(controller: scenario, maxLines: 3, maxLength: 4000, decoration: const InputDecoration(labelText: 'Scenario')),
        DropdownButtonFormField<String>(initialValue: appearanceStyle, decoration: const InputDecoration(labelText: 'Appearance style'),
          items: const ['classic','cinematic','anime','illustrated','realistic'].map((x) => DropdownMenuItem(value: x, child: Text(x))).toList(),
          onChanged: (v) => setState(() => appearanceStyle = v ?? 'classic')),
        TextField(controller: appearance, maxLines: 3, maxLength: 1500, decoration: const InputDecoration(labelText: 'Visual appearance / clothing / features')),
        TextField(controller: accent, maxLength: 7, decoration: const InputDecoration(labelText: 'Character accent color (#RRGGBB)')),
        TextField(controller: advanced, maxLines: 5, maxLength: 10000, decoration: const InputDecoration(labelText: 'Advanced definition', helperText: 'Roleplay reference; not a secure instruction boundary')),
        TextField(controller: tags, decoration: const InputDecoration(labelText: 'Tags (comma-separated, up to 10)')),
        const SizedBox(height: 12),
        Text('Greeting variations', style: Theme.of(context).textTheme.titleMedium),
        ...List.generate(greetings.length, (i) => Row(children: [
          Expanded(child: TextField(controller: greetings[i], maxLines: 2, maxLength: 2000, decoration: InputDecoration(labelText: 'Greeting ${i+1}'))),
          IconButton(tooltip: 'Remove greeting', onPressed: greetings.length <= 1 ? null : () => setState(() => greetings.removeAt(i).dispose()), icon: const Icon(Icons.remove_circle_outline)),
        ])),
        TextButton.icon(onPressed: greetings.length >= 8 ? null : () => setState(() => greetings.add(TextEditingController())), icon: const Icon(Icons.add), label: const Text('Add greeting')),
        TextField(controller: examples, maxLines: 6, decoration: const InputDecoration(labelText: 'Example dialogue', helperText: 'One line per turn: user: Hello / assistant: Hi!')),
        SwitchListTile(value: isPublic, title: const Text('Publish publicly'), onChanged: (v) => setState(() => isPublic = v)),
        const Divider(),
        Text('Creator test (not saved)', style: Theme.of(context).textTheme.titleMedium),
        TextField(controller: previewInput, maxLength: 1000, decoration: const InputDecoration(labelText: 'Test message')),
        OutlinedButton.icon(onPressed: busy ? null : preview, icon: const Icon(Icons.science_outlined), label: const Text('Preview with local Ollama')),
        if (previewResult != null) SelectableText(previewResult!),
        const SizedBox(height: 12),
        FilledButton.icon(onPressed: busy ? null : save, icon: const Icon(Icons.save_outlined), label: Text(widget.existing == null ? 'Create character' : 'Save changes')),
      ]),
    )),
  );
}

class ChatScreen extends StatefulWidget {
  final Api api;
  final String conversationId;
  final String characterName;
  const ChatScreen({super.key, required this.api, required this.conversationId, required this.characterName});
  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final input = TextEditingController();
  final scroll = ScrollController();
  final voicePlayer = AudioPlayer();
  bool voicePlaying = false;
  Future<void> playVoice(String messageId) async {
    try {
      if (mounted) setState(() => voicePlaying = true);
      final bytes = await widget.api.synthesizeMessage(widget.conversationId, messageId);
      await voicePlayer.stop();
      await voicePlayer.play(BytesSource(bytes));
    } catch (e) {
      if (mounted) showError(context, e);
    } finally {
      if (mounted) setState(() => voicePlaying = false);
    }
  }
  Future<void> audioLibrary() async {
    await showDialog<void>(context: context, builder: (_) => VoiceClipDialog(
      loadClips: () => widget.api.voiceClips(widget.conversationId),
      clipBytes: widget.api.voiceClipBytes,
      deleteClip: widget.api.deleteVoiceClip,
    ));
  }

  List<Map<String, dynamic>> messages = [];
  StreamSubscription<Map<String, dynamic>>? generation;
  Completer<void>? generationDone;
  bool sending = false;
  String draftReply = '';
  Map<String, dynamic>? lastDiagnostics;
  Map<String, dynamic>? lastQuality;
  int responseLength = 384;
  String? inferenceModel;
  String generationPreset = "balanced";
  double? temperature;
  double? topP;
  int? contextWindow;
  bool roleplayMode = true;
  bool groupMode = false;
  String mainCharacterId = "";
  String? backgroundMediaId;
  String? personaId;
  List<dynamic> participants = [];
  List<dynamic> availablePersonas = [];
  @override
  void initState() { super.initState(); load(); loadOptions(); }
  Future<void> load() async {
    try {
      final items = await widget.api.messages(widget.conversationId);
      if (mounted) setState(() => messages = items.map((e) => Map<String, dynamic>.from(e)).toList());
    } catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> loadOptions() async {
    try {
      final chats = await widget.api.conversations();
      final c = chats.firstWhere((e) => e['id'] == widget.conversationId);
      if (mounted) setState(() {
        responseLength = c['response_length'] as int? ?? 384;
        inferenceModel = c['inference_model'] as String?;
        generationPreset = c['generation_preset'] as String? ?? 'balanced';
        temperature = (c['temperature'] as num?)?.toDouble();
        topP = (c['top_p'] as num?)?.toDouble();
        contextWindow = c['context_window'] as int?;
        roleplayMode = c['roleplay_mode'] as bool? ?? true;
        backgroundMediaId = c['background_media_id'] as String?;
        groupMode = c['chat_mode'] == 'group';
        mainCharacterId = c['character_id']?.toString() ?? '';
        personaId = c['persona_id'] as String?;
      });
      if (c['chat_mode'] == 'group') {
        final roster = await widget.api.groupParticipants(widget.conversationId);
        if (mounted) setState(() => participants = roster);
      }
      final profiles = await widget.api.personas();
      if (mounted) setState(() => availablePersonas = profiles);
    } catch (e) { if (mounted) showError(context, e); }
  }
  void toBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (scroll.hasClients) scroll.animateTo(scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 180), curve: Curves.easeOut);
    });
  }
  Future<void> stop() async {
    final active = generation;
    if (active == null) return;
    await active.cancel(); // Close HTTP stream so the backend cancels local inference.
    generation = null;
    if (generationDone != null && !generationDone!.isCompleted) generationDone!.complete();
    if (mounted) { setState(() { sending = false; draftReply = ''; }); await load(); }
  }
  Future<void> generate({String? regenerateId, bool retry = false, bool groupTurn = false, String? speakerId}) async {
    if (sending) return;
    final text = input.text.trim();
    if (regenerateId == null && !retry && !groupTurn && text.isEmpty) return;
    if (!groupTurn) input.clear();
    setState(() { sending = true; draftReply = ''; });
    toBottom();
    final completer = Completer<void>();
    generationDone = completer;
    bool finished = false;
    void finish() { if (!finished) { finished = true; completer.complete(); } }
    try {
      generation = widget.api.streamReply(widget.conversationId, text,
        regenerateId: regenerateId, retry: retry, groupTurn: groupTurn, speakerId: speakerId).listen((event) {
          if (!mounted) return;
          switch (event['event']) {
            case 'token':
              setState(() => draftReply += (event['text']?.toString() ?? ''));
              toBottom();
            case 'diagnostics':
              setState(() => lastDiagnostics = Map<String, dynamic>.from(event)..remove('event'));
            case 'quality':
              setState(() => lastQuality = Map<String, dynamic>.from(event)..remove('event'));
            case 'error':
              showError(context, event['message']?.toString() ?? 'Generation failed');
            case 'done':
              finish();
          }
        }, onError: (Object error) {
          if (mounted) showError(context, error);
          finish();
        }, onDone: finish, cancelOnError: true);
      await completer.future;
    } catch (e) { if (mounted) showError(context, e); }
    finally {
      await generation?.cancel();
      generation = null;
      generationDone = null;
      if (mounted) { setState(() { sending = false; draftReply = ''; }); await load(); toBottom(); }
    }
  }
  Future<void> edit(Map<String, dynamic> m) async {
    final controller = TextEditingController(text: m['content']?.toString() ?? '');
    final changed = await showDialog<String>(context: context, builder: (ctx) => AlertDialog(
      title: const Text('Edit message — creates a new branch'),
      content: TextField(controller: controller, maxLength: 4000, maxLines: 5),
      actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(ctx, controller.text.trim()), child: const Text('Save'))],
    ));
    controller.dispose();
    if (changed == null || changed.isEmpty) return;
    try { await widget.api.editMessage(widget.conversationId, m['id'] as String, changed); await load(); }
    catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> remove(Map<String, dynamic> m) async {
    final confirmed = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(
      title: const Text('Delete message and subsequent replies?'),
      content: const Text('This deletes the selected message and all descendant branches permanently.'),
      actions: [TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete'))]));
    if (confirmed != true) return;
    try { await widget.api.deleteMessage(widget.conversationId, m['id'] as String); await load(); }
    catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> fork(Map<String, dynamic> m) async {
    try {
      final id = await widget.api.branch(widget.conversationId, m['id'] as String);
      if (!mounted) return;
      await Navigator.push(context, MaterialPageRoute(builder: (_) => ChatScreen(
        api: widget.api, conversationId: id, characterName: widget.characterName)));
      await load();
    } catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> swipe(Map<String, dynamic> m) async {
    try {
      final variants = await widget.api.alternatives(widget.conversationId, m['id'] as String);
      if (!mounted || variants.isEmpty) return;
      final selected = await showDialog<String>(context: context, builder: (ctx) => SimpleDialog(
        title: const Text('Select generated reply'),
        children: [for (int i = 0; i < variants.length; i++) SimpleDialogOption(
          onPressed: () => Navigator.pop(ctx, variants[i]['id'] as String),
          child: Text('${i + 1}/${variants.length}: ${variants[i]['content']}', maxLines: 3, overflow: TextOverflow.ellipsis))]));
      if (selected != null) { await widget.api.selectAlternative(widget.conversationId, selected); await load(); }
    } catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> pickPersona() async {
    try {
      final profiles = await widget.api.personas();
      if (!mounted) return;
      final selected = await showDialog<String>(context: context, builder: (ctx) => SimpleDialog(
        title: const Text('Select your roleplay persona'), children: [
          SimpleDialogOption(onPressed: () => Navigator.pop(ctx, '__none__'), child: const Text('No persona')),
          ...profiles.map((p) => SimpleDialogOption(onPressed: () => Navigator.pop(ctx, p['id'] as String), child: Text(p['name'].toString()))),
        ]));
      if (selected == null) return;
      final newId = selected == '__none__' ? null : selected;
      await widget.api.selectPersona(widget.conversationId, newId);
      if (mounted) setState(() { personaId = newId; availablePersonas = profiles; });
    } catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> chooseGroupSpeaker() async {
    if (sending || messages.isEmpty || participants.isEmpty) return;
    final selected = await showDialog<String>(context: context, builder: (ctx) => SimpleDialog(
      title: const Text('Who speaks next?'), children: [
        SimpleDialogOption(onPressed: () => Navigator.pop(ctx, '__auto__'), child: const Text('Next character (round-robin)')),
        ...participants.map((p) => SimpleDialogOption(onPressed: () => Navigator.pop(ctx, p['character_id'] as String), child: Text(p['name'].toString()))),
      ]));
    if (selected != null) await generate(groupTurn: true, speakerId: selected == '__auto__' ? null : selected);
  }
  Future<void> settings() async {
    await Navigator.push(context, MaterialPageRoute(builder: (_) => ChatModelSettingsScreen(
      api: widget.api, conversationId: widget.conversationId,
      initialModel: inferenceModel, initialPreset: generationPreset,
      initialTemperature: temperature, initialTopP: topP,
      initialContext: contextWindow, initialTokens: responseLength, initialRoleplay: roleplayMode,
    )));
    if (mounted) await loadOptions();
  }

  Future<void> showPromptDiagnostics() async {
    try {
      final data = lastDiagnostics ?? await widget.api.promptDiagnostics(widget.conversationId);
      if (!mounted) return;
      await showDialog<void>(context: context, builder: (ctx) => AlertDialog(
        title: const Text('Local prompt diagnostics'),
        content: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 470),
          child: SingleChildScrollView(child: PromptDiagnosticDetails(
            diagnostics: data, quality: lastQuality))),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close'))],
      ));
    } catch (e) { if (mounted) showError(context, e); }
  }

  @override
  void dispose() { generation?.cancel(); voicePlayer.dispose(); input.dispose(); scroll.dispose(); super.dispose(); }
  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(widget.characterName, maxLines: 1, overflow: TextOverflow.ellipsis),
      Text(widget.api.offlineMode ? 'Offline · saved messages only' : groupMode ? 'Group roleplay' : 'Character conversation', style: Theme.of(context).textTheme.labelSmall),
    ]), actions: [
      IconButton(tooltip: 'Select persona', icon: const Icon(Icons.badge_outlined), onPressed: sending ? null : pickPersona),
      if (groupMode) IconButton(tooltip: 'Next group speaker', icon: const Icon(Icons.record_voice_over_outlined), onPressed: sending || messages.isEmpty ? null : chooseGroupSpeaker),
      IconButton(tooltip: 'Prompt diagnostics', icon: const Icon(Icons.analytics_outlined), onPressed: showPromptDiagnostics),
      IconButton(tooltip: 'Chat settings', icon: const Icon(Icons.tune), onPressed: sending ? null : settings),
      IconButton(tooltip: 'Audio library', icon: const Icon(Icons.library_music_outlined), onPressed: audioLibrary),
      IconButton(tooltip: 'Chat background', icon: const Icon(Icons.wallpaper_outlined), onPressed: sending ? null : () async {
        await Navigator.push(context, MaterialPageRoute(builder: (_) => MediaManagerScreen(api: widget.api, scope: 'conversation', scopeId: widget.conversationId, canEdit: true)));
        if (mounted) await loadOptions();
      }),
      IconButton(tooltip: 'Story & roleplay', icon: const Icon(Icons.auto_stories_outlined),
        onPressed: sending ? null : () => Navigator.push(context, MaterialPageRoute(builder: (_) =>
          StoryWorkspace(api: widget.api, conversationId: widget.conversationId,
            mainCharacterId: mainCharacterId, mainCharacterName: widget.characterName,
            participants: participants))),
      IconButton(tooltip: 'Memory center', icon: const Icon(Icons.psychology_outlined),
        onPressed: sending ? null : () => showDialog<void>(context: context,
          builder: (_) => MemoryDialog(api: widget.api, conversationId: widget.conversationId))),
    ]),
    body: PageFrame(maxWidth: 1000, padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Column(children: [
        Expanded(child: Stack(fit: StackFit.expand, children: [
          if (backgroundMediaId != null) Opacity(opacity: 0.20, child: PrivateMediaImage(api: widget.api, mediaId: backgroundMediaId!)),
          messages.isEmpty && !sending
          ? const EmptyView(icon: Icons.auto_awesome_outlined, title: 'Start the conversation',
              message: 'Say hello or begin your roleplay.')
          : ListView.builder(controller: scroll,
            padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
            itemCount: messages.length + (sending ? 1 : 0), itemBuilder: (context, i) {
              if (i == messages.length) return ChatBubble(isUser: false,
                speaker: 'Character · generating', content: draftReply.isEmpty ? 'Thinking…' : draftReply);
              final m = messages[i]; final isUser = m['role'] == 'user';
              final speaker = !isUser && groupMode ? participants
                .where((p) => p['character_id'] == m['speaker_character_id'])
                .map((p) => p['name']?.toString() ?? 'Character').firstOrNull : null;
              return ChatBubble(isUser: isUser, content: m['content']?.toString() ?? '', speaker: speaker,
                actions: Wrap(spacing: 0, children: [
                  IconButton(icon: const Icon(Icons.edit_outlined, size: 18), tooltip: 'Edit (new path)', onPressed: sending ? null : () => edit(m)),
                  IconButton(icon: const Icon(Icons.account_tree_outlined, size: 18), tooltip: 'Fork chat here', onPressed: sending ? null : () => fork(m)),
                  IconButton(icon: const Icon(Icons.delete_outline, size: 18), tooltip: 'Delete from here', onPressed: sending ? null : () => remove(m)),
                  if (!isUser) ...[
                    IconButton(icon: const Icon(Icons.volume_up_outlined, size: 18), tooltip: 'Read aloud', onPressed: sending || voicePlaying ? null : () => playVoice(m['id'] as String)),
                    IconButton(icon: const Icon(Icons.swap_horiz, size: 18), tooltip: 'Swipe alternatives', onPressed: sending ? null : () => swipe(m)),
                    if (i == messages.length - 1) IconButton(icon: const Icon(Icons.refresh, size: 18), tooltip: 'Regenerate reply',
                      onPressed: sending ? null : () => generate(regenerateId: m['id'] as String)),
                  ],
                ]));
            }),
        ])),
        if (groupMode && messages.isNotEmpty && !sending) TextButton.icon(
          onPressed: chooseGroupSpeaker, icon: const Icon(Icons.groups_outlined), label: const Text('Next character speaks')),
        if (messages.isNotEmpty && messages.last['role'] == 'user' && !sending)
          TextButton.icon(onPressed: () => generate(retry: true), icon: const Icon(Icons.refresh), label: const Text('Retry unanswered message')),
        SafeArea(top: false, child: Padding(padding: const EdgeInsets.all(10), child: Row(children: [
          Expanded(child: TextField(controller: input, minLines: 1, maxLines: 5,
            textCapitalization: TextCapitalization.sentences,
            decoration: const InputDecoration(hintText: 'Write a message…', prefixIcon: Icon(Icons.edit_note_outlined)),
            onSubmitted: (_) => generate())),
          const SizedBox(width: 6),
          VoiceRecorderButton(
            onTranscribe: widget.api.transcribeAudio,
            onTranscript: (text) { input.text = [input.text.trim(), text.trim()]
                .where((s) => s.isNotEmpty).join(' '); },
          ),
          const SizedBox(width: 10),
          if (sending) IconButton.filled(tooltip: 'Stop generating', onPressed: stop, icon: const Icon(Icons.stop_circle_outlined))
          else IconButton.filled(tooltip: 'Send', onPressed: () => generate(), icon: const Icon(Icons.arrow_upward)),
        ]))),
      ])),
  );

}

// The character profile is a dedicated details page. Only creators can edit.
class CharacterProfileScreen extends StatefulWidget {
  final Api api;
  final String characterId;
  final Future<void> Function(Map<String, dynamic>, int) onChat;
  const CharacterProfileScreen({super.key, required this.api, required this.characterId, required this.onChat});
  @override
  State<CharacterProfileScreen> createState() => _CharacterProfileScreenState();
}
class _CharacterProfileScreenState extends State<CharacterProfileScreen> {
  Map<String, dynamic>? character;
  bool owner = false;
  bool loading = true;
  @override
  void initState() { super.initState(); load(); }
  Future<void> load() async {
    try {
      final profile = await widget.api.character(widget.characterId);
      final me = Map<String, dynamic>.from(await widget.api.request('GET', '/users/me'));
      if (mounted) setState(() { character = profile; owner = profile['creator_id'] == me['id']; loading = false; });
    } catch (e) { if (mounted) { setState(() => loading = false); showError(context, e); } }
  }
  Future<void> edit() async {
    if (character == null) return;
    final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) =>
        CharacterEditorScreen(api: widget.api, existing: character)));
    if (saved == true) await load();
  }
  Future<void> voiceSettings() async {
    if (character == null) return;
    try {
      final status = await widget.api.voiceStatus();
      if (!mounted) return;
      final voices = (status['voices'] as List? ?? ['default']).map((e) => e.toString()).toList();
      if (voices.isEmpty) throw Exception('No voice models configured');
      final selected = await showDialog<String>(context: context, builder: (ctx) => SimpleDialog(
        title: const Text('Character voice'),
        children: voices.map((v) => SimpleDialogOption(onPressed: () => Navigator.pop(ctx, v), child: Text(v))).toList(),
      ));
      if (selected != null) {
        await widget.api.setCharacterVoice(widget.characterId, selected);
        await load();
      }
    } catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> export() async {
    try {
      final json = const JsonEncoder.withIndent('  ').convert(await widget.api.exportCharacter(widget.characterId));
      if (!mounted) return;
      await showDialog<void>(context: context, builder: (context) => AlertDialog(
        title: const Text('Export character JSON'),
        content: SizedBox(width: 560, height: 320, child: SingleChildScrollView(child: SelectableText(json))),
        actions: [TextButton(onPressed: () async {
          await Clipboard.setData(ClipboardData(text: json));
          if (context.mounted) Navigator.pop(context);
        }, child: const Text('Copy JSON')),
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))],
      ));
    } catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> chooseGreeting() async {
    final c = character;
    if (c == null) return;
    final variants = (c['greetings'] as List? ?? []);
    final options = variants.isEmpty ? [c['greeting'] ?? 'Hello!'] : variants;
    if (options.length == 1) { await widget.onChat(c, 0); return; }
    final choice = await showDialog<int>(context: context, builder: (context) => SimpleDialog(
      title: const Text('Choose a first message'),
      children: List.generate(options.length, (i) => SimpleDialogOption(
        onPressed: () => Navigator.pop(context, i), child: Text('${i+1}. ${options[i]}', maxLines: 3, overflow: TextOverflow.ellipsis))),
    ));
    if (choice != null && mounted) await widget.onChat(c, choice);
  }
  @override
  Widget build(BuildContext context) {
    final c = character;
    return Scaffold(
      appBar: AppBar(title: const Text('Character profile'),
        actions: [IconButton(tooltip: 'Lorebook', onPressed: () => showDialog<void>(context: context,
          builder: (_) => LorebookDialog(api: widget.api, characterId: widget.characterId, owner: owner)),
          icon: const Icon(Icons.menu_book_outlined)),
          if (owner) IconButton(tooltip: 'Preferred AI model', onPressed: () async {
            await Navigator.push(context, MaterialPageRoute(builder: (_) => CharacterModelSettingsScreen(api: widget.api, characterId: widget.characterId, initialModel: character?['preferred_model'] as String?)));
            await load();
          }, icon: const Icon(Icons.memory_outlined)),
          IconButton(tooltip: 'Character images', onPressed: () async {
            await Navigator.push(context, MaterialPageRoute(builder: (_) => MediaManagerScreen(
              api: widget.api, scope: 'character', scopeId: widget.characterId, canEdit: owner)));
            if (mounted) setState(() {});
          }, icon: const Icon(Icons.photo_library_outlined)),
          if (owner) IconButton(tooltip: 'Export JSON', onPressed: export, icon: const Icon(Icons.ios_share_outlined)),
          if (owner) IconButton(tooltip: 'Character voice', onPressed: voiceSettings, icon: const Icon(Icons.record_voice_over_outlined)),
          if (owner) IconButton(tooltip: 'Edit character', onPressed: edit, icon: const Icon(Icons.edit_outlined))]),
      body: loading ? const Center(child: CircularProgressIndicator()) : c == null
        ? const Center(child: Text('Character unavailable'))
        : Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 840),
          child: ListView(padding: const EdgeInsets.all(24), children: [
            FutureBuilder<List<dynamic>>(future: widget.api.mediaList('character', widget.characterId),
              builder: (ctx, snap) {
                final matches = (snap.data ?? []).where((m) => m['purpose'] == 'avatar').toList();
                if (matches.isNotEmpty) return Center(child: ClipOval(child: PrivateMediaImage(api: widget.api, mediaId: matches.first['id'] as String, width: 112, height: 112)));
                return Center(child: CircleAvatar(radius: 56, child: Text((c['name']?.toString().isNotEmpty == true ? c['name'].toString().substring(0, 1) : '?').toUpperCase(), style: const TextStyle(fontSize: 40))));
              }),
            const SizedBox(height: 12),
            SizedBox(height: 88, child: FutureBuilder<List<dynamic>>(
              future: widget.api.mediaList('character', widget.characterId),
              builder: (context, snap) {
                final gallery = (snap.data ?? []).where((m) => m['purpose'] == 'gallery').toList();
                return ListView(scrollDirection: Axis.horizontal, children: gallery.map((m) => Padding(
                  padding: const EdgeInsets.only(right: 8), child: ClipRRect(borderRadius: BorderRadius.circular(10),
                    child: PrivateMediaImage(api: widget.api, mediaId: m['id'] as String, width: 88, height: 88)))).toList());
              })),
            const SizedBox(height: 16),
            Text(c['name'] ?? '',  textAlign: TextAlign.center, style: Theme.of(context).textTheme.headlineMedium),
            Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Text(c['tagline'] ?? '', textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleMedium)),
            const SizedBox(height: 20),
            FilledButton.icon(onPressed: chooseGreeting, icon: const Icon(Icons.chat_bubble_outline), child: const Text('Start new conversation')),
            const SizedBox(height: 20),
            CharacterCommunityPanel(api: widget.api, characterId: widget.characterId, creatorId: c['creator_id'] as String,
              isPublic: c['is_public'] == true, onOpenCreator: () => Navigator.push(context, MaterialPageRoute(
                builder: (_) => CreatorScreen(api: widget.api, creatorId: c['creator_id'] as String, onOpen: (profile) async {
                  Navigator.pop(context);
                  if (!mounted) return;
                  await Navigator.push(context, MaterialPageRoute(builder: (_) => CharacterProfileScreen(
                    api: widget.api, characterId: profile['id'] as String, onChat: widget.onChat)));
                })))),
            const SizedBox(height: 20),
            Center(child: Chip(label: Text(c['is_public'] == true ? 'Public character' : 'Private character'))),
            const SizedBox(height: 10),
            if ((c['appearance_description']?.toString() ?? '').isNotEmpty) ...[
              Text('Appearance · ${c['appearance_style'] ?? 'classic'}', style: Theme.of(context).textTheme.titleLarge),
              Text(c['appearance_description'].toString()), const SizedBox(height: 14)],
            Text('Personality', style: Theme.of(context).textTheme.titleLarge),
            Text(c['personality'] ?? ''),
            const SizedBox(height: 16),
            Text('Scenario', style: Theme.of(context).textTheme.titleLarge),
            Text(c['scenario'] ?? ''),
            const SizedBox(height: 16),
            Text('First message', style: Theme.of(context).textTheme.titleLarge),
            Text(c['greeting'] ?? ''),
            if ((c['greetings'] as List? ?? []).length > 1) Text('${(c['greetings'] as List).length} greeting variations'),
            if ((c['tags'] as List? ?? []).isNotEmpty) Wrap(spacing: 6, children: (c['tags'] as List).map((t) => Chip(label: Text(t.toString()))).toList()),
          ]))),
    );
  }
}

// Pinned memory is manually managed, persistent and isolated per conversation.
class MemoryDialog extends StatefulWidget {
  final Api api;
  final String conversationId;
  const MemoryDialog({super.key, required this.api, required this.conversationId});
  @override
  State<MemoryDialog> createState() => _MemoryDialogState();
}
class _MemoryDialogState extends State<MemoryDialog> {
  final input = TextEditingController();
  List<dynamic> items = [];
  bool busy = false;
  bool autoMemory = false;
  List<dynamic> learned = [];
  String recap = '';
  @override
  void initState() { super.initState(); refresh(); }
  @override
  void dispose() { input.dispose(); super.dispose(); }
  Future<void> refresh() async {
    try {
      final data = await widget.api.memories(widget.conversationId);
      final learnedData = await widget.api.learnedMemories(widget.conversationId);
      final summaryData = await widget.api.summary(widget.conversationId);
      final conversations = await widget.api.conversations();
      final chat = conversations.cast<Map<String, dynamic>>().firstWhere(
        (c) => c['id'] == widget.conversationId, orElse: () => {});
      if (mounted) setState(() { items = data; learned = learnedData;
        recap = summaryData['content']?.toString() ?? '';
        autoMemory = chat['auto_memory'] == true; });
    } catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> add() async {
    if (input.text.trim().isEmpty || busy) return;
    setState(() => busy = true);
    try {
      await widget.api.addMemory(widget.conversationId, input.text.trim());
      input.clear();
      await refresh();
    } catch (e) { if (mounted) showError(context, e); }
    finally { if (mounted) setState(() => busy = false); }
  }
  Future<void> remove(String id) async {
    try {
      await widget.api.deleteMemory(widget.conversationId, id);
      await refresh();
    } catch (e) { if (mounted) showError(context, e); }
  }
  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Memory center'),
    content: SizedBox(width: 460, child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [
      SwitchListTile(title: const Text('Automatic memory'),
        subtitle: const Text('Opt in to local AI extraction of facts and recaps.'),
        value: autoMemory, onChanged: (value) async {
          try { await widget.api.editConversation(widget.conversationId, {'auto_memory': value});
            if (mounted) setState(() => autoMemory = value);
          } catch (e) { if (mounted) showError(context, e); }
        }),
      const Text('Pinned notes: manually saved in this conversation.'),
      const SizedBox(height: 12),
      ConstrainedBox(constraints: const BoxConstraints(maxHeight: 320), child: ListView(
        shrinkWrap: true, children: [
          if (items.isEmpty) const ListTile(title: Text('No pinned memories yet')),
          ...items.map((m) => ListTile(
            title: Text(m['content']?.toString() ?? ''),
            trailing: IconButton(icon: const Icon(Icons.delete_outline), tooltip: 'Forget this note',
              onPressed: () => remove(m['id'] as String)),
          )),
        ],
      )),
      const Divider(),
      const Text('Learned memories', style: TextStyle(fontWeight: FontWeight.bold)),
      if (learned.isEmpty) const ListTile(title: Text('No learned memories yet')),
      ConstrainedBox(constraints: const BoxConstraints(maxHeight: 160), child: ListView(shrinkWrap: true,
        children: learned.map((m) => ListTile(dense: true,
          subtitle: Text(m['category']?.toString() ?? 'fact'),
          title: Text(m['content']?.toString() ?? ''),
          trailing: Wrap(mainAxisSize: MainAxisSize.min, children: [
            IconButton(tooltip: 'Edit memory', icon: const Icon(Icons.edit_outlined), onPressed: () async {
              final controller = TextEditingController(text: m['content']?.toString() ?? '');
              final updated = await showDialog<String>(context: context, builder: (ctx) => AlertDialog(
                title: const Text('Edit learned memory'), content: TextField(controller: controller, maxLength: 400),
                actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
                FilledButton(onPressed: () => Navigator.pop(ctx, controller.text.trim()), child: const Text('Save'))]));
              controller.dispose();
              if (updated != null && updated.isNotEmpty) {
                try { await widget.api.editLearned(widget.conversationId, m['id'] as String, updated); await refresh(); }
                catch (e) { if (mounted) showError(context, e); }
              }
            }),
            IconButton(tooltip: 'Forget learned memory', icon: const Icon(Icons.delete_outline), onPressed: () async {
              try { await widget.api.deleteLearned(widget.conversationId, m['id'] as String); await refresh(); }
              catch (e) { if (mounted) showError(context, e); }
            }),
          ])),
        ).toList())),
      const Divider(),
      const Text('Conversation recap', style: TextStyle(fontWeight: FontWeight.bold)),
      Text(recap.isEmpty ? 'No recap yet (created after eight exchanges with automatic memory enabled).' : recap),
      if (recap.isNotEmpty) TextButton.icon(onPressed: () async {
        try { await widget.api.clearSummary(widget.conversationId); await refresh(); }
        catch (e) { if (mounted) showError(context, e); }
      }, icon: const Icon(Icons.delete_outline), label: const Text('Clear recap')),
      const Divider(),
      TextField(controller: input, maxLength: 1200, maxLines: 2,
        decoration: const InputDecoration(labelText: 'New memory note')),
    ]))),
    actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close')),
      FilledButton(onPressed: busy || items.length >= 20 ? null : add, child: const Text('Pin memory'))],
  );
}


class LorebookDialog extends StatefulWidget {
  final Api api;
  final String characterId;
  final bool owner;
  const LorebookDialog({super.key, required this.api, required this.characterId, required this.owner});
  @override
  State<LorebookDialog> createState() => _LorebookDialogState();
}
class _LorebookDialogState extends State<LorebookDialog> {
  List<dynamic> entries = [];
  @override
  void initState() { super.initState(); refresh(); }
  Future<void> refresh() async {
    try { final data = await widget.api.lorebook(widget.characterId);
      if (mounted) setState(() => entries = data);
    } catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> editor([Map<String, dynamic>? entry]) async {
    final title = TextEditingController(text: entry?['title']?.toString() ?? '');
    final keywords = TextEditingController(text: entry?['keywords']?.toString() ?? '');
    final content = TextEditingController(text: entry?['content']?.toString() ?? '');
    try {
      final data = await showDialog<Map<String, dynamic>>(context: context, builder: (ctx) => AlertDialog(
        title: Text(entry == null ? 'Add lorebook entry' : 'Edit lorebook entry'),
        content: SizedBox(width: 460, child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: title, maxLength: 100, decoration: const InputDecoration(labelText: 'Title')),
          TextField(controller: keywords, maxLength: 400, decoration: const InputDecoration(labelText: 'Trigger keywords (space-separated)')),
          TextField(controller: content, maxLength: 1600, maxLines: 5, decoration: const InputDecoration(labelText: 'Lore / world information')),
        ]))),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, {'title': title.text.trim(),
            'keywords': keywords.text.trim(), 'content': content.text.trim()}), child: const Text('Save'))],
      ));
      if (data != null) {
        if (entry == null) { await widget.api.addLore(widget.characterId, data); }
        else { await widget.api.editLore(widget.characterId, entry['id'] as String, data); }
        await refresh();
      }
    } catch (e) { if (mounted) showError(context, e); }
    finally { title.dispose(); keywords.dispose(); content.dispose(); }
  }
  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Character lorebook'),
    content: SizedBox(width: 490, child: ConstrainedBox(constraints: const BoxConstraints(maxHeight: 480),
      child: ListView(shrinkWrap: true, children: [
        const Text('Lorebook entries activate when their keywords appear in the latest message.'),
        if (entries.isEmpty) const ListTile(title: Text('No lorebook entries')),
        ...entries.map((raw) { final entry = Map<String, dynamic>.from(raw as Map);
          return ListTile(title: Text(entry['title']?.toString() ?? ''),
            subtitle: Text('${entry['keywords'] ?? ''}\n${entry['content'] ?? ''}'),
            isThreeLine: true,
            trailing: widget.owner ? Wrap(mainAxisSize: MainAxisSize.min, children: [
              IconButton(tooltip: 'Edit entry', icon: const Icon(Icons.edit_outlined), onPressed: () => editor(entry)),
              IconButton(tooltip: 'Delete entry', icon: const Icon(Icons.delete_outline), onPressed: () async {
                try { await widget.api.deleteLore(widget.characterId, entry['id'] as String); await refresh(); }
                catch (e) { if (mounted) showError(context, e); }
              }),
            ]) : null);
        }),
      ]))),
    actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close')),
      if (widget.owner) FilledButton.icon(onPressed: entries.length >= 100 ? null : () => editor(),
        icon: const Icon(Icons.add), label: const Text('Add entry'))],
  );
}


// v0.6: private user personas, independent from character definitions.
class PersonaManagerScreen extends StatefulWidget {
  final Api api;
  const PersonaManagerScreen({super.key, required this.api});
  @override
  State<PersonaManagerScreen> createState() => _PersonaManagerScreenState();
}
class _PersonaManagerScreenState extends State<PersonaManagerScreen> {
  List<dynamic> personas = [];
  @override
  void initState() { super.initState(); reload(); }
  Future<void> reload() async {
    try { final items = await widget.api.personas(); if (mounted) setState(() => personas = items); }
    catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> editor([Map<String, dynamic>? original]) async {
    final name = TextEditingController(text: original?['name']?.toString() ?? '');
    final bio = TextEditingController(text: original?['biography']?.toString() ?? '');
    final avatar = TextEditingController(text: original?['avatar_url']?.toString() ?? '');
    try {
      final result = await showDialog<Map<String, dynamic>>(context: context, builder: (ctx) => AlertDialog(
        title: Text(original == null ? 'New persona' : 'Edit persona'),
        content: SizedBox(width: 520, child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: name, maxLength: 80, decoration: const InputDecoration(labelText: 'Name')),
          TextField(controller: bio, maxLength: 3000, maxLines: 5, decoration: const InputDecoration(labelText: 'Biography / roleplay identity')),
          TextField(controller: avatar, maxLength: 500, decoration: const InputDecoration(labelText: 'Avatar URL (HTTPS, optional)')),
        ]))), actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, {'name': name.text.trim(), 'biography': bio.text.trim(), 'avatar_url': avatar.text.trim()}), child: const Text('Save'))]));
      if (result == null) return;
      if (original == null) { await widget.api.addPersona(result); }
      else { await widget.api.editPersona(original['id'] as String, result); }
      await reload();
    } catch (e) { if (mounted) showError(context, e); }
    finally { name.dispose(); bio.dispose(); avatar.dispose(); }
  }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('My personas'), actions: [IconButton(onPressed: () => editor(), icon: const Icon(Icons.add), tooltip: 'Add persona')]),
    body: ListView(children: [
      if (personas.isEmpty) const ListTile(title: Text('No personas yet'), subtitle: Text('Create a roleplay identity for your chats.')),
      ...personas.map((p) => ListTile(
        leading: FutureBuilder<List<dynamic>>(future: widget.api.mediaList('persona', p['id'] as String),
          builder: (ctx, snap) {
            final matches = (snap.data ?? []).where((m) => m['purpose'] == 'avatar').toList();
            return matches.isNotEmpty
              ? ClipOval(child: PrivateMediaImage(api: widget.api, mediaId: matches.first['id'] as String, width: 42, height: 42))
              : CircleAvatar(
                  backgroundImage: (p['avatar_url']?.toString().startsWith('https://') ?? false)
                    ? NetworkImage(p['avatar_url'] as String) : null,
                  child: (p['avatar_url']?.toString().startsWith('https://') ?? false)
                    ? null : const Icon(Icons.face_outlined));
          }),
        title: Text(p['name'].toString()), subtitle: Text(p['biography']?.toString() ?? '', maxLines: 2),
        isThreeLine: true,
        onTap: () => editor(Map<String, dynamic>.from(p)),
        trailing: Row(mainAxisSize: MainAxisSize.min, children: [
          IconButton(tooltip: 'Persona avatar uploads', onPressed: () => Navigator.push(context, MaterialPageRoute(
            builder: (_) => MediaManagerScreen(api: widget.api, scope: 'persona', scopeId: p['id'] as String, canEdit: true))), icon: const Icon(Icons.image_outlined)),
          IconButton(tooltip: 'Delete persona', icon: const Icon(Icons.delete_outline), onPressed: () async {
          final yes = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(
            title: const Text('Delete persona?'), content: const Text('Chats keep their messages, but will no longer use this persona.'),
            actions: [TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
              FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete'))]));
          if (yes == true) { try { await widget.api.deletePersona(p['id'] as String); await reload(); }
          catch (e) { if (mounted) showError(context, e); } }
        })]),
      )),
    ]),
  );
}

class GroupCreatorScreen extends StatefulWidget {
  final Api api;
  const GroupCreatorScreen({super.key, required this.api});
  @override
  State<GroupCreatorScreen> createState() => _GroupCreatorScreenState();
}
class _GroupCreatorScreenState extends State<GroupCreatorScreen> {
  final title = TextEditingController(text: 'Group roleplay');
  final scenario = TextEditingController();
  List<dynamic> options = [];
  List<dynamic> identities = [];
  final Set<String> selected = {};
  String? personaId;
  bool submitting = false;
  @override
  void initState() { super.initState(); load(); }
  Future<void> load() async {
    try {
      final public = await widget.api.characters();
      final mine = await widget.api.mine();
      final unique = <String, dynamic>{};
      for (final c in [...public, ...mine]) { unique[c['id'] as String] = c; }
      final allPersonas = await widget.api.personas();
      if (mounted) setState(() { options = unique.values.toList(); identities = allPersonas; });
    } catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> save() async {
    if (selected.length < 2 || selected.length > 6 || submitting) return;
    setState(() => submitting = true);
    try {
      final ids = options.where((c) => selected.contains(c['id'])).map<String>((c) => c['id'] as String).toList();
      final id = await widget.api.startGroup(ids, title.text.trim(), scenario.text.trim(), personaId);
      if (mounted) Navigator.pop(context, id);
    } catch (e) { if (mounted) showError(context, e); }
    finally { if (mounted) setState(() => submitting = false); }
  }
  @override
  void dispose() { title.dispose(); scenario.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Create group roleplay')),
    body: ListView(padding: const EdgeInsets.all(18), children: [
      TextField(controller: title, maxLength: 120, decoration: const InputDecoration(labelText: 'Group title')),
      TextField(controller: scenario, maxLength: 4000, maxLines: 4, decoration: const InputDecoration(labelText: 'Group story / scenario')),
      DropdownButtonFormField<String>(value: personaId, decoration: const InputDecoration(labelText: 'Your persona (optional)'),
        items: [const DropdownMenuItem<String>(value: null, child: Text('No persona')),
          ...identities.map((p) => DropdownMenuItem<String>(value: p['id'] as String, child: Text(p['name'].toString())))],
        onChanged: (v) => setState(() => personaId = v)),
      const SizedBox(height: 16),
      Text('Select 2–6 characters (${selected.length} chosen)', style: Theme.of(context).textTheme.titleMedium),
      ...options.map((c) => CheckboxListTile(title: Text(c['name'].toString()), subtitle: Text(c['tagline']?.toString() ?? ''),
        value: selected.contains(c['id']), onChanged: (v) => setState(() {
          if (v == true && selected.length < 6) { selected.add(c['id'] as String); }
          if (v == false) selected.remove(c['id']);
        }))),
      const SizedBox(height: 12),
      FilledButton.icon(onPressed: selected.length >= 2 && !submitting ? save : null,
        icon: const Icon(Icons.groups_outlined), label: const Text('Create group')),
    ]),
  );
}
