import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:character_chat_client/main.dart';

void main() {
  testWidgets('switches between registration and sign in without server', (tester) async {
    await tester.pumpWidget(MaterialApp(home: LoginScreen(api: Api(), onLogin: () {})));
    await tester.tap(find.text('Create an account'));
    await tester.pump();
    expect(find.text('Display name'), findsOneWidget);
    expect(find.text('Create account'), findsOneWidget);
    await tester.tap(find.text('Already registered? Sign in'));
    await tester.pump();
    expect(find.text('Display name'), findsNothing);
    expect(find.text('Sign in'), findsOneWidget);
  });
}
