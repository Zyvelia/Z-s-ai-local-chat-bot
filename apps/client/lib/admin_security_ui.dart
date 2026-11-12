import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'main.dart';

class PrivacyScreen extends StatefulWidget {
  final Api api;
  final VoidCallback onDeleted;
  const PrivacyScreen({super.key, required this.api, required this.onDeleted});
  @override State<PrivacyScreen> createState() => _PrivacyScreenState();
}
class _PrivacyScreenState extends State<PrivacyScreen> {
  List<dynamic> appeals = [];
  bool busy = false;
  @override void initState() { super.initState(); load(); }
  Future<void> load() async {
    try { final values = await widget.api.myAppeals(); if (mounted) setState(() => appeals = values); }
    catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> export() async {
    try {
      setState(() => busy = true);
      final data = await widget.api.myAccountExport();
      await Clipboard.setData(ClipboardData(text: const JsonEncoder.withIndent('  ').convert(data)));
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Your account data was copied as JSON. Store it privately.')));
    } catch (e) { if (mounted) showError(context, e); }
    finally { if (mounted) setState(() => busy = false); }
  }
  Future<void> appeal() async {
    final reason = TextEditingController();
    final character = TextEditingController();
    try {
      final sent = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(
        title: const Text('Submit an appeal'),
        content: SizedBox(width: 480, child: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: character, decoration: const InputDecoration(labelText: 'Character ID (optional)')),
          TextField(controller: reason, maxLines: 4, maxLength: 2000,
              decoration: const InputDecoration(labelText: 'Appeal explanation (10+ characters)')),
        ])),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Submit'))],
      ));
      if (sent != true) return;
      await widget.api.submitAppeal(reason.text.trim(), characterId: character.text.trim().isEmpty ? null : character.text.trim());
      await load();
    } catch (e) { if (mounted) showError(context, e); }
    finally { reason.dispose(); character.dispose(); }
  }
  Future<void> delete() async {
    final confirmation = TextEditingController();
    try {
      final accepted = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(
        title: const Text('Permanently delete account?'),
        content: SizedBox(width: 430, child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Text('This removes your account, characters, chats, and memories. Chats other users had with your characters may also be removed. This cannot be undone. Export data first.'),
          TextField(controller: confirmation, decoration: const InputDecoration(labelText: 'Type DELETE to confirm')),
        ])),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, confirmation.text == 'DELETE'), child: const Text('Delete account'))],
      ));
      if (accepted != true) return;
      await widget.api.deleteMyAccount();
      widget.api.token = null;
      widget.onDeleted();
      if (mounted) Navigator.pop(context);
    } catch (e) { if (mounted) showError(context, e); }
    finally { confirmation.dispose(); }
  }
  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Privacy & Appeals')),
    body: ListView(padding: const EdgeInsets.all(16), children: [
      ListTile(title: const Text('Export account data'), subtitle: const Text('Copies your data as JSON to the clipboard'),
        trailing: const Icon(Icons.download), onTap: busy ? null : export),
      ListTile(title: const Text('Submit an appeal'), trailing: const Icon(Icons.gavel), onTap: appeal),
      const Divider(), const Text('Your appeals', style: TextStyle(fontSize: 18)),
      ...appeals.map((a) => ListTile(title: Text(a['reason']?.toString() ?? ''),
          subtitle: Text('Status: ${a['status']} · ${a['response'] ?? ''}'))),
      const Divider(),
      ListTile(title: const Text('Delete account permanently'),
        subtitle: const Text('This also deletes authored characters and associated chats'),
        textColor: Theme.of(context).colorScheme.error,
        trailing: const Icon(Icons.delete_forever), onTap: delete),
    ]),
  );
}

class AdminScreen extends StatefulWidget {
  final Api api;
  const AdminScreen({super.key, required this.api});
  @override State<AdminScreen> createState() => _AdminScreenState();
}
class _AdminScreenState extends State<AdminScreen> {
  Map<String, dynamic>? stats, performance;
  List<dynamic> users = [], reports = [], appeals = [], events = [];
  bool busy = true;
  String? error;
  @override void initState() { super.initState(); load(); }
  Future<void> load() async {
    try {
      final values = await Future.wait([widget.api.adminDashboard(), widget.api.adminUsers(),
        widget.api.adminReports(), widget.api.adminAppeals(), widget.api.adminAudit(), widget.api.adminPerformance()]);
      if (mounted) setState(() { stats = Map<String, dynamic>.from(values[0] as Map);
        users = values[1] as List; reports = values[2] as List; appeals = values[3] as List;
        events = values[4] as List; performance = Map<String, dynamic>.from(values[5] as Map); busy = false; error = null; });
    } catch (e) { if (mounted) setState(() { busy = false; error = e.toString(); }); }
  }
  Future<String?> prompt(String title) async {
    final value = TextEditingController();
    try { return await showDialog<String>(context: context, builder: (ctx) => AlertDialog(
      title: Text(title), content: TextField(controller: value, autofocus: true,
          maxLength: 500, decoration: const InputDecoration(labelText: 'Reason / response')),
      actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(ctx, value.text.trim()), child: const Text('Confirm'))])); }
    finally { value.dispose(); }
  }
  Future<void> action(Future<void> Function() task) async {
    try { await task(); await load(); } catch (e) { if (mounted) showError(context, e); }
  }
  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Admin dashboard'), actions: [IconButton(icon: const Icon(Icons.refresh), onPressed: load)]),
    body: busy ? const Center(child: CircularProgressIndicator()) : error != null ?
      Center(child: Text(error!)) : ListView(padding: const EdgeInsets.all(16), children: [
      Text('Users: ${stats?['users']} · Characters: ${stats?['characters']} · Chats: ${stats?['conversations']}'),
      Text('Open reports: ${stats?['open_reports']} · Open appeals: ${stats?['open_appeals']}'),
      const SizedBox(height: 20), const Text('Platform performance', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
      Text('Coordination: ${performance?['redis'] ?? 'unknown'}'),
      Text('Inference: ${performance?['queue']?['running'] ?? '—'} running / ${performance?['queue']?['waiting'] ?? '—'} waiting'),
      Text('API successes: ${performance?['api']?['ok_requests'] ?? 0} · Errors: ${performance?['api']?['error_requests'] ?? 0}'),
      const SizedBox(height: 20), const Text('Reports', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
      ...reports.map((r) => ListTile(title: Text('${r['reason']} · ${r['status']}'),
        subtitle: Text('Character ${r['character_id']} · ${r['details']}'),
        trailing: PopupMenuButton<String>(onSelected: (value) => action(() => widget.api.adminReportDecision(r['id'].toString(), value)),
          itemBuilder: (_) => ['reviewing','resolved','dismissed'].map((x) => PopupMenuItem(value: x, child: Text(x))).toList()))),
      const Divider(), const Text('Appeals', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
      ...appeals.map((a) => ListTile(title: Text('${a['status']} · ${a['user_id']}'),
        subtitle: Text(a['reason'].toString()),
        trailing: PopupMenuButton<String>(onSelected: (value) async {
          final response = await prompt('Respond to appeal');
          if (response != null && response.length >= 3) await action(() => widget.api.adminAppealDecision(a['id'].toString(), value, response));
        }, itemBuilder: (_) => ['accepted','rejected'].map((x) => PopupMenuItem(value: x, child: Text(x))).toList()))),
      const Divider(), const Text('Users', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
      ...users.map((u) => ListTile(title: Text(u['display_name'].toString()),
        subtitle: Text('${u['email']} · ${u['role']} · ${u['is_suspended'] == true ? 'Suspended' : 'Active'}'),
        trailing: PopupMenuButton<String>(onSelected: (value) async {
          final reason = value == 'suspend' ? await prompt('Reason for suspension') : '';
          if (reason == null || (value == 'suspend' && reason.isEmpty)) return;
          await action(() => widget.api.adminRestrict(u['id'].toString(), value == 'suspend', reason));
        }, itemBuilder: (_) => ['suspend','restore'].map((x) => PopupMenuItem(value: x, child: Text(x))).toList()))),
      const Divider(), const Text('Moderate character by ID', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
      TextButton(onPressed: () async {
        final id = await prompt('Character ID to hide');
        if (id == null || id.isEmpty) return;
        final reason = await prompt('Why hide this character?');
        if (reason == null || reason.length < 3) return;
        await action(() => widget.api.adminModerate(id, 'hidden', reason));
      }, child: const Text('Hide character')),
      TextButton(onPressed: () async {
        final id = await prompt('Character ID to restore');
        if (id == null || id.isEmpty) return;
        final reason = await prompt('Reason for restoration');
        if (reason == null || reason.length < 3) return;
        await action(() => widget.api.adminModerate(id, 'active', reason));
      }, child: const Text('Restore character')),
      const Divider(), const Text('Recent audit events', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
      ...events.map((e) => ListTile(dense: true, title: Text(e['action'].toString()),
        subtitle: Text('${e['target_type']}: ${e['target_id']}'))),
    ]),
  );
}
