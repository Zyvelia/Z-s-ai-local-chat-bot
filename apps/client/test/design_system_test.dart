import 'package:character_chat_client/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('responsive breakpoints scale to phone, tablet, desktop', () {
    expect(AppLayout.isWide(390), isFalse);
    expect(AppLayout.isTablet(700), isTrue);
    expect(AppLayout.isWide(1080), isTrue);
    expect(AppLayout.gridColumns(390), 1);
    expect(AppLayout.gridColumns(600), 2);
    expect(AppLayout.gridColumns(900), 3);
    expect(AppLayout.gridColumns(1280), 4);
  });

  testWidgets('character tiles surface discoverable text and tap', (tester) async {
    var opened = false;
    await tester.pumpWidget(MaterialApp(theme: AppThemes.build(Brightness.dark), home:
      Scaffold(body: Center(child: SizedBox(width: 340, height: 230, child:
        CharacterTile(character: const {'name': 'Nova', 'tagline': 'A curious explorer', 'tags': ['Mystery']},
          onTap: () => opened = true))))));
    expect(find.text('Nova'), findsOneWidget);
    expect(find.text('A curious explorer'), findsOneWidget);
    await tester.tap(find.text('Nova'));
    expect(opened, isTrue);
  });

  testWidgets('empty view explains state and includes action', (tester) async {
    var used = false;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: EmptyView(
      icon: Icons.inbox_outlined, title: 'No chats', message: 'Start a new conversation',
      action: FilledButton(onPressed: () => used = true, child: const Text('Create'))))));
    expect(find.text('No chats'), findsOneWidget);
    await tester.tap(find.text('Create'));
    expect(used, isTrue);
  });

  testWidgets('retry view exposes recovery action', (tester) async {
    var retried = false;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: RetryView(
      message: 'Server unreachable', onRetry: () => retried = true))));
    expect(find.text('Server unreachable'), findsOneWidget);
    await tester.tap(find.text('Try again'));
    expect(retried, isTrue);
  });

  testWidgets('chat bubbles display selectable messages and speaker labels', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: ChatBubble(
      content: 'Hello, traveler', isUser: false, speaker: 'Nova'))));
    expect(find.text('Nova'), findsOneWidget);
    expect(find.byType(SelectableText), findsOneWidget);
    expect(find.text('Hello, traveler'), findsOneWidget);
  });

  test('light and dark themes preserve their brightness', () {
    expect(AppThemes.build(Brightness.light).colorScheme.brightness, Brightness.light);
    expect(AppThemes.build(Brightness.dark).colorScheme.brightness, Brightness.dark);
  });
}
