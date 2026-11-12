import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:character_chat_client/story_ui.dart';

void main() {
  testWidgets('Story empty state starts the scenario flow', (tester) async {
    var tapped = 0;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body:
        Center(child: StoryStartPrompt(onCreate: () => tapped++)))));
    expect(find.textContaining('No story yet'), findsOneWidget);
    await tester.tap(find.text('Start story'));
    expect(tapped, 1);
  });
  testWidgets('Start story provides semantic action', (tester) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body:
        StoryStartPrompt(onCreate: () {}))));
    expect(find.byIcon(Icons.auto_stories_outlined), findsOneWidget);
    expect(find.byType(FilledButton), findsOneWidget);
  });
}
