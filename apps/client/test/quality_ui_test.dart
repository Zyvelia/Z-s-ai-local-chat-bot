import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:character_chat_client/quality_ui.dart';

void main() {
  testWidgets('diagnostics show estimated budget and repetition advisory', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: SingleChildScrollView(child:
      PromptDiagnosticDetails(diagnostics: {
        'context_window': 4096, 'estimated_input_tokens': 1200,
        'reserved_output_and_headroom': 600, 'history_messages_included': 9,
        'history_messages_skipped': 4,
        'sections': [{'name': 'character_identity', 'estimated_tokens': 300, 'truncated': false}],
      }, quality: {'repetition_similarity': 0.95, 'possibly_repetitive': true})))));
    expect(find.textContaining('4096'), findsOneWidget);
    expect(find.textContaining('character_identity'), findsOneWidget);
    expect(find.textContaining('Possible repetition'), findsOneWidget);
  });
}
