import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:character_chat_client/voice_audio_ui.dart';

void main() {
  test('PCM is wrapped into little-endian mono WAV correctly', () {
    final wav = pcmToWav(Uint8List.fromList([1, 2, 3, 4]));
    expect(String.fromCharCodes(wav.sublist(0, 4)), 'RIFF');
    expect(String.fromCharCodes(wav.sublist(8, 12)), 'WAVE');
    expect(ByteData.sublistView(wav).getUint32(24, Endian.little), 16000);
    expect(ByteData.sublistView(wav).getUint32(40, Endian.little), 4);
    expect(wav.sublist(44), [1, 2, 3, 4]);
  });

  test('An odd PCM byte is dropped to preserve sample boundaries', () {
    final wav = pcmToWav(Uint8List.fromList([1, 2, 3]));
    expect(wav.length, 46);
    expect(ByteData.sublistView(wav).getUint32(40, Endian.little), 2);
  });

  testWidgets('Recorder exposes a microphone tooltip', (tester) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: VoiceRecorderButton(
      onTranscribe: (_) async => 'hello', onTranscript: (_) {},
    ))));
    expect(find.byTooltip('Record voice message (max 30 seconds)'), findsOneWidget);
  });

  testWidgets('Audio library has an empty state', (tester) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: Builder(builder: (context) =>
      TextButton(onPressed: () => showDialog<void>(context: context, builder: (_) => VoiceClipDialog(
        loadClips: () async => [], clipBytes: (_) async => Uint8List(0), deleteClip: (_) async {},
      )), child: const Text('Open'))))));
    await tester.tap(find.text('Open'));
    await tester.pump(); await tester.pump();
    expect(find.textContaining('No audio saved'), findsOneWidget);
  });
}
