import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:character_chat_client/main.dart';

void main() {
  testWidgets('login mode displays sign-in fields', (tester) async {
    await tester.pumpWidget(MaterialApp(home: LoginScreen(api: Api(), onLogin: () {})));
    expect(find.text('Character Chat'), findsOneWidget);
    expect(find.text('Sign in'), findsOneWidget);
    expect(find.text('Email'), findsOneWidget);
    expect(find.text('Password (10+ characters)'), findsOneWidget);
  });
}
