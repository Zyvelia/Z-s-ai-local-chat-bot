import 'package:flutter/material.dart';
import 'main.dart';

/// Administrative read-only diagnostics; Ollama is never exposed directly to clients.
class ModelHealthScreen extends StatefulWidget {
  final Api api;
  const ModelHealthScreen({super.key, required this.api});
  @override
  State<ModelHealthScreen> createState() => _ModelHealthScreenState();
}

class _ModelHealthScreenState extends State<ModelHealthScreen> {
  Map<String, dynamic>? status;
  List<dynamic> models = [];
  String? error;
  @override
  void initState() { super.initState(); refresh(); }
  Future<void> refresh() async {
    try {
      final results = await Future.wait([widget.api.localHealth(), widget.api.localModels()]);
      if (mounted) setState(() {
        status = results[0];
        models = (results[1]['models'] as List?) ?? [];
        error = null;
      });
    } catch (e) { if (mounted) setState(() => error = '$e'); }
  }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Self-hosted AI status'), actions: [
      IconButton(onPressed: refresh, tooltip: 'Refresh', icon: const Icon(Icons.refresh))]),
    body: ListView(padding: const EdgeInsets.all(20), children: [
      if (error != null) Text(error!, style: const TextStyle(color: Colors.orange)),
      if (status == null) const LinearProgressIndicator() else ...[
        ListTile(title: Text(status!['online'] == true ? 'Ollama: online' : 'Ollama: offline'),
          subtitle: Text('Version: ${status!['version'] ?? 'Unknown'}')),
        ListTile(title: const Text('Inference queue'),
          subtitle: Text('Running: ${status!['queue']?['running']}, waiting: ${status!['queue']?['waiting']}, '
              'capacity: ${status!['queue']?['capacity']} (per backend process)')),
        const Text('Currently loaded models', style: TextStyle(fontWeight: FontWeight.bold)),
        if (status!['loaded_models'] == null) const ListTile(title: Text('Runtime model data unavailable')),
        ...((status!['loaded_models'] as List?) ?? []).map((m) => ListTile(
          title: Text('${m['name']}'),
          subtitle: Text('GPU-resident bytes: ${m['size_vram'] ?? 'unknown'}'))),
        const Text('GPU-resident bytes describe model allocation, not live GPU load or utilization.'),
      ],
      const SizedBox(height: 14),
      const Text('Installed models', style: TextStyle(fontWeight: FontWeight.bold)),
      ...models.map((m) => ListTile(title: Text('${m['name']}'), subtitle: Text('Disk size (bytes): ${m['size'] ?? 'unknown'}'))),
      const Text('Models are installed by the server operator using Ollama. Public users cannot download or remove server models.'),
    ]),
  );
}

class CharacterModelSettingsScreen extends StatefulWidget {
  final Api api;
  final String characterId;
  final String? initialModel;
  const CharacterModelSettingsScreen({super.key, required this.api, required this.characterId, required this.initialModel});
  @override
  State<CharacterModelSettingsScreen> createState() => _CharacterModelSettingsScreenState();
}
class _CharacterModelSettingsScreenState extends State<CharacterModelSettingsScreen> {
  List<String> models = [];
  String? selected;
  bool saving = false;
  @override
  void initState() { super.initState(); selected = widget.initialModel; load(); }
  Future<void> load() async {
    try {
      final values = await widget.api.localModels();
      if (mounted) setState(() => models = (values['models'] as List).map((x) => x['name'].toString()).toList());
    } catch (e) { if (mounted) showError(context, e); }
  }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Preferred character model')),
    body: ListView(padding: const EdgeInsets.all(20), children: [
      DropdownButtonFormField<String>(value: selected != null && models.contains(selected) ? selected : '',
        decoration: const InputDecoration(labelText: 'Local Ollama model'),
        items: [const DropdownMenuItem(value: '', child: Text('Server default')),
          ...models.map((name) => DropdownMenuItem(value: name, child: Text(name)))],
        onChanged: (v) => setState(() => selected = v == '' ? null : v)),
      const SizedBox(height: 16),
      FilledButton(onPressed: saving ? null : () async {
        setState(() => saving = true);
        try {
          await widget.api.setCharacterModel(widget.characterId, selected);
          if (context.mounted) Navigator.pop(context);
        } catch (e) { if (context.mounted) showError(context, e); }
        finally { if (mounted) setState(() => saving = false); }
      }, child: const Text('Save model preference')),
    ]),
  );
}

class ChatModelSettingsScreen extends StatefulWidget {
  final Api api;
  final String conversationId;
  final String? initialModel;
  final String initialPreset;
  final double? initialTemperature;
  final double? initialTopP;
  final int? initialContext;
  final int initialTokens;
  final bool initialRoleplay;
  const ChatModelSettingsScreen({super.key, required this.api, required this.conversationId,
    required this.initialModel, required this.initialPreset, required this.initialTemperature,
    required this.initialTopP, required this.initialContext, required this.initialTokens, required this.initialRoleplay});
  @override
  State<ChatModelSettingsScreen> createState() => _ChatModelSettingsScreenState();
}
class _ChatModelSettingsScreenState extends State<ChatModelSettingsScreen> {
  List<String> models = [];
  late String? selected;
  late String preset;
  late double temp;
  late double topP;
  late int contextWindow;
  late int maxTokens;
  bool saving = false;
  late bool roleplay;
  final presets = const ['balanced', 'creative', 'precise', 'roleplay', 'custom'];
  @override
  void initState() {
    super.initState();
    selected = widget.initialModel;
    preset = widget.initialPreset;
    temp = widget.initialTemperature ?? 0.7;
    topP = widget.initialTopP ?? 0.9;
    contextWindow = widget.initialContext ?? 4096;
    maxTokens = widget.initialTokens;
    roleplay = widget.initialRoleplay;
    load();
  }
  Future<void> load() async {
    try {
      final data = await widget.api.localModels();
      if (mounted) setState(() => models = (data['models'] as List).map((x) => x['name'].toString()).toList());
    } catch (e) { if (mounted) showError(context, e); }
  }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('AI generation settings')),
    body: ListView(padding: const EdgeInsets.all(20), children: [
      DropdownButtonFormField<String>(value: selected != null && models.contains(selected) ? selected : '',
        decoration: const InputDecoration(labelText: 'Ollama model override'),
        items: [const DropdownMenuItem(value: '', child: Text('Use character preference / server default')),
          ...models.map((name) => DropdownMenuItem(value: name, child: Text(name)))],
        onChanged: (v) => setState(() => selected = v == '' ? null : v)),
      const SizedBox(height: 12),
      DropdownButtonFormField<String>(value: preset, decoration: const InputDecoration(labelText: 'Preset'),
        items: presets.map((name) => DropdownMenuItem(value: name, child: Text(name))).toList(),
        onChanged: (v) => setState(() => preset = v ?? 'balanced')),
      const SizedBox(height: 12),
      Text('Temperature: ${temp.toStringAsFixed(2)}'),
      Slider(value: temp, min: 0, max: 2, divisions: 40, onChanged: (v) => setState(() { temp = v; preset = 'custom'; })),
      Text('Top-P: ${topP.toStringAsFixed(2)}'),
      Slider(value: topP, min: 0.05, max: 1, divisions: 19, onChanged: (v) => setState(() { topP = v; preset = 'custom'; })),
      Text('Context window: $contextWindow tokens'),
      Slider(value: contextWindow.toDouble().clamp(512, 32768).toDouble(), min: 512, max: 32768, divisions: 63,
        onChanged: (v) => setState(() => contextWindow = v.round())),
      Text('Max response length: $maxTokens tokens'),
      Slider(value: maxTokens.toDouble().clamp(64, 2048).toDouble(), min: 64, max: 2048, divisions: 31,
        onChanged: (v) => setState(() => maxTokens = v.round())),
      const SizedBox(height: 12),
      SwitchListTile(title: const Text('Roleplay formatting'), value: roleplay,
        onChanged: (v) => setState(() => roleplay = v)),
      FilledButton(onPressed: saving ? null : () async {
        setState(() => saving = true);
        try {
          await widget.api.setChatInference(widget.conversationId, {
            'inference_model': selected, 'generation_preset': preset,
            'temperature': preset == 'custom' ? temp : null,
            'top_p': preset == 'custom' ? topP : null,
            'context_window': contextWindow, 'response_length': maxTokens,
          });
          await widget.api.editConversation(widget.conversationId, {'roleplay_mode': roleplay});
          if (context.mounted) Navigator.pop(context);
        } catch (e) { if (context.mounted) showError(context, e); }
        finally { if (mounted) setState(() => saving = false); }
      }, child: const Text('Save inference settings')),
      const SizedBox(height: 10),
      const Text('Preset parameters override temperature and Top-P except when Custom is selected.'),
    ]),
  );
}
