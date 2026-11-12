import 'package:character_chat_client/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeApi extends Api {
  @override Future<List<dynamic>> characters() async => [
    {'id': 'nova', 'name': 'Nova', 'tagline': 'An explorer', 'tags': ['Adventure']},
  ];
  @override Future<List<dynamic>> mine() async => [];
  @override Future<List<dynamic>> conversations() async => [];
}

void main() {
  testWidgets('mobile has bottom navigation and can switch tabs', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(home: HomeScreen(api: FakeApi(), onLogout: () {})));
    await tester.pumpAndSettle();
    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.byType(NavigationRail), findsNothing);
    expect(find.text('Nova'), findsOneWidget);
    await tester.tap(find.text('Chats').last);
    await tester.pumpAndSettle();
    expect(find.text('No conversations'), findsOneWidget);
  });

  testWidgets('desktop uses expanded navigation rail', (tester) async {
    tester.view.physicalSize = const Size(1280, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(home: HomeScreen(api: FakeApi(), onLogout: () {})));
    await tester.pumpAndSettle();
    expect(find.byType(NavigationRail), findsOneWidget);
    expect(find.byType(NavigationBar), findsNothing);
  });
}
