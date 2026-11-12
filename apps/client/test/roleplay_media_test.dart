import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:character_chat_client/design_system.dart';
import 'package:character_chat_client/media_ui.dart';

void main() {
  test('Roleplay markup separates actions and bold dialogue', () {
    final spans = RoleplayText.spans('*walks* Hello **friend**', Colors.purple);
    expect(spans.length, 3);
    expect(spans[0].text, 'walks');
    expect(spans[0].style?.fontStyle, FontStyle.italic);
    expect(spans.last.text, 'friend');
    expect(spans.last.style?.fontWeight, FontWeight.bold);
  });

  testWidgets('Roleplay is readable with assistive text selection', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: RoleplayText(content: '*waves* Hello'))));
    expect(find.byType(SelectableText), findsOneWidget);
  });

  testWidgets('Media image displays placeholder during loading', (tester) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: PrivateMediaImage(api: FakeMediaApi(), mediaId: 'test', width: 80, height: 80))));
    expect(find.byIcon(Icons.image_outlined), findsOneWidget);
  });
}

class FakeMediaApi {
  Future<Uint8List> mediaBytes(String id) => Completer<Uint8List>().future;
}
