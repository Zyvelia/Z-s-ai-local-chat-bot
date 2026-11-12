import 'package:flutter/material.dart';
import 'main.dart' show Api;

/// A private story workspace. Each operation uses authenticated endpoints.
class StoryWorkspace extends StatefulWidget {
  final Api api;
  final String conversationId;
  final String mainCharacterId;
  final String mainCharacterName;
  final List<dynamic> participants;
  const StoryWorkspace({super.key, required this.api, required this.conversationId,
    required this.mainCharacterId, this.mainCharacterName = 'Main character', this.participants = const []});
  @override State<StoryWorkspace> createState() => _StoryWorkspaceState();
}

class _StoryWorkspaceState extends State<StoryWorkspace> {
  bool busy = true;
  String? error;
  Map<String, dynamic>? story;
  List<dynamic> scenes = [], timeline = [], relationships = [], emotions = [], scenarios = [];
  String get base => '/conversations/${widget.conversationId}/story';
  Future<void> refresh() async {
    setState(() { busy = true; error = null; });
    try {
      Map<String, dynamic>? state;
      try {
        state = Map<String, dynamic>.from(await widget.api.request('GET', base));
      } catch (e) {
        if (!e.toString().contains('Story not initialized')) rethrow;
      }
      final a = state == null ? <dynamic>[] : await widget.api.request('GET', '$base/scenes') as List;
      final b = state == null ? <dynamic>[] : await widget.api.request('GET', '$base/timeline') as List;
      final c = state == null ? <dynamic>[] : await widget.api.request('GET', '$base/relationships') as List;
      final d = state == null ? <dynamic>[] : await widget.api.request('GET', '$base/emotions') as List;
      final e = await widget.api.request('GET', '/story/scenarios') as List;
      if (mounted) setState(() { story = state; scenes = a; timeline = b; relationships = c; emotions = d; scenarios = e; });
    } catch (e) { if (mounted) setState(() => error = '$e'); }
    finally { if (mounted) setState(() => busy = false); }
  }
  @override void initState() { super.initState(); refresh(); }

  Future<Map<String, String>?> editFields(String title, Map<String, String> fields) async {
    final controllers = {for (final e in fields.entries) e.key: TextEditingController(text: e.value)};
    try {
      return await showDialog<Map<String, String>>(context: context, builder: (ctx) => AlertDialog(
        title: Text(title), content: SizedBox(width: 440, child: SingleChildScrollView(child: Column(
        mainAxisSize: MainAxisSize.min, children: [for (final e in controllers.entries)
          Padding(padding: const EdgeInsets.only(bottom: 8), child: TextField(
          controller: e.value, maxLength: e.key == 'premise' ? 2000 : 500,
          maxLines: e.key == 'premise' || e.key == 'setting' || e.key == 'details' ? 3 : 1,
          decoration: InputDecoration(labelText: e.key)))]))),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, {
            for (final e in controllers.entries) e.key: e.value.text.trim()}), child: const Text('Save'))]));
    } finally { for (final c in controllers.values) { c.dispose(); } }
  }
  Future<void> perform(Future<dynamic> Function() operation) async {
    try { await operation(); if (mounted) await refresh(); }
    catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e'))); }
  }
  Future<void> initialize() async {
    final fields = await editFields('Start a story', {'title': 'Untitled story', 'premise': '', 'objective': ''});
    if (fields == null || fields['title']!.isEmpty) return;
    await perform(() async => widget.api.request('PUT', base, {...fields, 'chapter': 1, 'status': 'active'}));
  }
  Future<void> editStory() async {
    final s = story!;
    final fields = await editFields('Story state', {'title': '${s['title']}', 'premise': '${s['premise']}',
      'objective': '${s['objective']}', 'chapter': '${s['chapter']}', 'status': '${s['status']}'});
    if (fields == null || fields['title']!.isEmpty) return;
    final chapter = int.tryParse(fields.remove('chapter') ?? '') ?? 1;
    final status = fields.remove('status') ?? 'active';
    await perform(() async => widget.api.request('PUT', base, {...fields,
      'chapter': chapter, 'status': ['active','paused','completed'].contains(status) ? status : 'active'}));
  }
  Future<void> addScene() async {
    final fields = await editFields('New scene', {'title': '', 'setting': '', 'goal': ''});
    if (fields == null || fields['title']!.isEmpty) return;
    await perform(() async => widget.api.request('POST', '$base/scenes', fields));
  }
  Future<void> editScene(Map<String, dynamic> scene) async {
    final fields = await editFields('Edit scene', {'title': '${scene['title']}',
      'setting': '${scene['setting']}', 'goal': '${scene['goal']}'});
    if (fields == null || fields['title']!.isEmpty) return;
    await perform(() async => widget.api.request('PATCH', '$base/scenes/${scene['id']}', fields));
  }
  Future<void> removeScene(Map<String, dynamic> scene) async {
    await perform(() async => widget.api.request('DELETE', '$base/scenes/${scene['id']}'));
  }
  Future<void> addEvent() async {
    final fields = await editFields('Timeline milestone', {'title': '', 'details': '', 'kind': 'milestone'});
    if (fields == null || fields['title']!.isEmpty) return;
    final kind = fields['kind']!;
    fields['kind'] = ['milestone','decision','discovery','relationship','scene'].contains(kind) ? kind : 'milestone';
    await perform(() async => widget.api.request('POST', '$base/timeline', fields));
  }
  Future<void> editCharacterState(String id, bool emotion) async {
    final list = emotion ? emotions : relationships;
    final current = list.where((e) => e['character_id'] == id).firstOrNull;
    final fields = await editFields(emotion ? 'Character emotion' : 'Relationship progression', emotion
        ? {'emotion': '${current?['emotion'] ?? 'neutral'}', 'intensity': '${current?['intensity'] ?? 50}', 'notes': '${current?['notes'] ?? ''}'}
        : {'affinity': '${current?['affinity'] ?? 0}', 'trust': '${current?['trust'] ?? 0}', 'notes': '${current?['notes'] ?? ''}'});
    if (fields == null) return;
    final data = emotion
        ? {'emotion': fields['emotion'], 'intensity': int.tryParse(fields['intensity'] ?? '') ?? 50, 'notes': fields['notes']}
        : {'affinity': int.tryParse(fields['affinity'] ?? '') ?? 0, 'trust': int.tryParse(fields['trust'] ?? '') ?? 0, 'notes': fields['notes']};
    await perform(() async => widget.api.request('PUT', '$base/${emotion ? 'emotions' : 'relationships'}/$id', data));
  }
  Future<void> saveScenario() async {
    if (story == null) return;
    final fields = await editFields('Save reusable scenario', {'title': '${story!['title']}',
      'premise': '${story!['premise']}', 'objective': '${story!['objective']}', 'opening_scene': ''});
    if (fields == null || fields['title']!.isEmpty) return;
    await perform(() async => widget.api.request('POST', '/story/scenarios', fields));
  }
  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Story & Roleplay'), actions: [IconButton(
      tooltip: 'Refresh story', onPressed: refresh, icon: const Icon(Icons.refresh))]),
    body: busy ? const Center(child: CircularProgressIndicator()) : error != null
      ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [Text(error!),
        TextButton(onPressed: refresh, child: const Text('Retry'))]))
      : story == null ? Center(child: StoryStartPrompt(onCreate: initialize))
      : ListView(padding: const EdgeInsets.all(16), children: [
          Card(child: ListTile(title: Text('${story!['title']} — Chapter ${story!['chapter']}'),
            subtitle: Text('${story!['premise']}\nObjective: ${story!['objective']}\nStatus: ${story!['status']}'),
            trailing: IconButton(tooltip: 'Edit story', icon: const Icon(Icons.edit), onPressed: editStory))),
          const SizedBox(height: 12),
          _header('Scenes', addScene),
          ...scenes.map((s) => Card(child: ListTile(title: Text('${s['title']}'),
            subtitle: Text('${s['setting']}\nGoal: ${s['goal']}'),
            selected: story!['current_scene_id'] == s['id'],
            trailing: Wrap(mainAxisSize: MainAxisSize.min, children: [
              IconButton(tooltip: 'Activate scene', icon: const Icon(Icons.play_arrow),
                onPressed: () => perform(() async => widget.api.request('PUT', '$base/scenes/${s['id']}/activate'))),
              IconButton(tooltip: 'Edit scene', icon: const Icon(Icons.edit_outlined),
                onPressed: () => editScene(Map<String, dynamic>.from(s))),
              IconButton(tooltip: 'Delete scene', icon: const Icon(Icons.delete_outline),
                onPressed: () => removeScene(Map<String, dynamic>.from(s))),
            ])))),
          _header('Character relationships & emotions', null),
          ...{widget.mainCharacterId, ...widget.participants.map((p) => p['character_id'].toString())}.map((id) =>
            Card(child: ListTile(title: Text(id == widget.mainCharacterId ? widget.mainCharacterName :
                widget.participants.where((p) => p['character_id'] == id).map((p) => p['name']?.toString() ?? id).firstOrNull ?? id),
              subtitle: Text('Set how this character feels and relates to your persona.'),
              trailing: Wrap(children: [TextButton(onPressed: () => editCharacterState(id, false), child: const Text('Relationship')),
                TextButton(onPressed: () => editCharacterState(id, true), child: const Text('Emotion'))])))),
          _header('Event timeline', addEvent),
          if (timeline.isEmpty) const ListTile(title: Text('No milestones recorded')),
          ...timeline.map((e) => ListTile(leading: const Icon(Icons.flag_outlined), title: Text('${e['title']}'),
            subtitle: Text('${e['kind']} · ${e['details']}'), trailing: IconButton(
              tooltip: 'Delete event', icon: const Icon(Icons.delete_outline), onPressed: () =>
                perform(() async => widget.api.request('DELETE', '$base/timeline/${e['id']}'))))),
          _header('My scenario templates', saveScenario),
          ...scenarios.map((s) => ListTile(title: Text('${s['title']}'), subtitle: Text('${s['premise']}'),
            trailing: TextButton(onPressed: () => perform(() async => widget.api.request('POST',
              '$base/scenarios/${s['id']}')), child: const Text('Apply')))),
          const SizedBox(height: 30),
        ]));
  Widget _header(String title, VoidCallback? add) => Padding(padding: const EdgeInsets.only(top: 16, bottom: 6),
    child: Row(children: [Expanded(child: Text(title, style: Theme.of(context).textTheme.titleMedium)),
      if (add != null) IconButton(tooltip: title == 'My scenario templates' ? 'Save scenario' : 'Add $title',
        icon: const Icon(Icons.add_circle_outline), onPressed: add)]));
}


/// Small independently testable empty state for new story conversations.
class StoryStartPrompt extends StatelessWidget {
  final VoidCallback onCreate;
  const StoryStartPrompt({super.key, required this.onCreate});
  @override Widget build(BuildContext context) => Column(mainAxisSize: MainAxisSize.min, children: [
    const Icon(Icons.auto_stories_outlined, size: 40),
    const Padding(padding: EdgeInsets.all(12), child: Text(
      'No story yet. Create one to track scenes and relationships.', textAlign: TextAlign.center)),
    FilledButton(onPressed: onCreate, child: const Text('Start story')),
  ]);
}
