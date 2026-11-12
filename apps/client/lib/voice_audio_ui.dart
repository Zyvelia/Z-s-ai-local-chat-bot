import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:record/record.dart';
import 'package:audioplayers/audioplayers.dart';

/// Wrap a bounded 16-bit mono PCM recording as a standard WAV file.
Uint8List pcmToWav(Uint8List pcm, {int sampleRate = 16000}) {
  final length = pcm.length - pcm.length % 2;
  final out = ByteData(44 + length);
  const riff = [82, 73, 70, 70], wave = [87, 65, 86, 69], fmt = [102, 109, 116, 32], data = [100, 97, 116, 97];
  void word(int off, List<int> letters) {
    for (var i = 0; i < letters.length; i++) { out.setUint8(off + i, letters[i]); }
  }
  word(0, riff); out.setUint32(4, 36 + length, Endian.little);
  word(8, wave); word(12, fmt); out.setUint32(16, 16, Endian.little);
  out.setUint16(20, 1, Endian.little); out.setUint16(22, 1, Endian.little);
  out.setUint32(24, sampleRate, Endian.little); out.setUint32(28, sampleRate * 2, Endian.little);
  out.setUint16(32, 2, Endian.little); out.setUint16(34, 16, Endian.little);
  word(36, data); out.setUint32(40, length, Endian.little);
  out.buffer.asUint8List().setRange(44, 44 + length, pcm);
  return out.buffer.asUint8List();
}

class VoiceRecorderButton extends StatefulWidget {
  final Future<String> Function(Uint8List) onTranscribe;
  final void Function(String) onTranscript;
  const VoiceRecorderButton({super.key, required this.onTranscribe, required this.onTranscript});
  @override State<VoiceRecorderButton> createState() => _VoiceRecorderButtonState();
}

class _VoiceRecorderButtonState extends State<VoiceRecorderButton> {
  final AudioRecorder recorder = AudioRecorder();
  final BytesBuilder chunks = BytesBuilder(copy: false);
  StreamSubscription<Uint8List>? sub;
  Timer? limit;
  bool recording = false;
  bool loading = false;
  static const maxBytes = 16000 * 2 * 30;
  Future<void> toggle() async {
    if (loading) return;
    if (recording) { await finish(); return; }
    try {
      if (!await recorder.hasPermission()) return;
      chunks.clear();
      final stream = await recorder.startStream(const RecordConfig(
        encoder: AudioEncoder.pcm16bits, sampleRate: 16000, numChannels: 1,
      ));
      sub = stream.listen((bytes) {
        if (chunks.length + bytes.length > maxBytes) {
          final room = maxBytes - chunks.length;
          if (room > 0) chunks.add(bytes.sublist(0, room));
          finish();
        } else {
          chunks.add(bytes);
        }
      }, onError: (_) => finish());
      limit = Timer(const Duration(seconds: 30), finish);
      if (mounted) setState(() => recording = true);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Microphone unavailable: $e')));
    }
  }
  Future<void> finish() async {
    if (!recording || loading) return;
    limit?.cancel();
    if (mounted) setState(() { recording = false; loading = true; });
    try {
      await recorder.stop();
      await sub?.cancel();
      final pcm = chunks.takeBytes();
      if (pcm.isNotEmpty) {
        final text = await widget.onTranscribe(pcmToWav(pcm));
        if (mounted && text.trim().isNotEmpty) widget.onTranscript(text);
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Speech recognition failed: $e')));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }
  @override void dispose() {
    limit?.cancel(); sub?.cancel(); recorder.dispose(); super.dispose();
  }
  @override Widget build(BuildContext context) => IconButton(
    tooltip: loading ? 'Transcribing speech' : recording ? 'Stop recording' : 'Record voice message (max 30 seconds)',
    onPressed: loading ? null : toggle,
    icon: loading ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
      : Icon(recording ? Icons.stop_circle_outlined : Icons.mic_none_outlined),
  );
}

class VoiceClipDialog extends StatefulWidget {
  final Future<List<dynamic>> Function() loadClips;
  final Future<Uint8List> Function(String) clipBytes;
  final Future<void> Function(String) deleteClip;
  const VoiceClipDialog({super.key, required this.loadClips, required this.clipBytes, required this.deleteClip});
  @override State<VoiceClipDialog> createState() => _VoiceClipDialogState();
}
class _VoiceClipDialogState extends State<VoiceClipDialog> {
  final player = AudioPlayer();
  List<dynamic> clips = [];
  bool loading = true;
  String? error;
  @override void initState() { super.initState(); refresh(); }
  Future<void> refresh() async {
    try {
      final result = await widget.loadClips();
      if (mounted) setState(() { clips = result; loading = false; error = null; });
    } catch (e) { if (mounted) setState(() { loading = false; error = e.toString(); }); }
  }
  Future<void> play(String id) async {
    try {
      final bytes = await widget.clipBytes(id);
      await player.stop(); await player.play(BytesSource(bytes));
    } catch (e) { if (mounted) setState(() => error = e.toString()); }
  }
  Future<void> remove(String id) async {
    try { await widget.deleteClip(id); await refresh(); }
    catch (e) { if (mounted) setState(() => error = e.toString()); }
  }
  @override void dispose() { player.dispose(); super.dispose(); }
  @override Widget build(BuildContext context) => AlertDialog(
    title: const Text('Saved voice clips'),
    content: SizedBox(width: 440, height: 360, child: loading
      ? const Center(child: CircularProgressIndicator())
      : Column(children: [
        if (error != null) Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
        Expanded(child: clips.isEmpty ? const Center(child: Text('No audio saved yet. Use Read aloud in chat.'))
          : ListView(children: clips.map((value) {
            final item = Map<String, dynamic>.from(value);
            final id = item['id'].toString();
            return ListTile(
              title: Text('Voice: ${item['voice_id']}'),
              subtitle: Text('${item['size_bytes']} bytes'),
              leading: IconButton(tooltip: 'Play clip', icon: const Icon(Icons.play_arrow), onPressed: () => play(id)),
              trailing: IconButton(tooltip: 'Delete clip', icon: const Icon(Icons.delete_outline), onPressed: () => remove(id)),
            );
          }).toList())),
      ])),
    actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close'))],
  );
}
