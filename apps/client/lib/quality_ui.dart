import 'package:flutter/material.dart';

/// No prompts or private message contents are displayed here, only estimated counts.
class PromptDiagnosticDetails extends StatelessWidget {
  final Map<String, dynamic> diagnostics;
  final Map<String, dynamic>? quality;
  const PromptDiagnosticDetails({super.key, required this.diagnostics, this.quality});

  @override
  Widget build(BuildContext context) {
    final sections = diagnostics['sections'];
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Token usage is estimated; the local model may count differently.'),
      const SizedBox(height: 12),
      Text('Context window: ${diagnostics['context_window'] ?? 'unknown'}'),
      Text('Estimated input tokens: ${diagnostics['estimated_input_tokens'] ?? 'unknown'}'),
      Text('Reserved output + headroom: ${diagnostics['reserved_output_and_headroom'] ?? 'unknown'}'),
      Text('History turns included: ${diagnostics['history_messages_included'] ?? 'unknown'}'),
      Text('Older turns skipped: ${diagnostics['history_messages_skipped'] ?? 'unknown'}'),
      if (sections is List) ...[
        const SizedBox(height: 12),
        const Text('Context sections', style: TextStyle(fontWeight: FontWeight.bold)),
        ...sections.whereType<Map>().map((item) => Text(
          '${item['name']}: ~${item['estimated_tokens']} tokens${item['truncated'] == true ? ' (truncated)' : ''}')),
      ],
      if (quality != null) ...[
        const SizedBox(height: 12),
        const Text('Last reply', style: TextStyle(fontWeight: FontWeight.bold)),
        Text('Repetition similarity: ${quality!['repetition_similarity'] ?? 'unknown'}'),
        if (quality!['possibly_repetitive'] == true)
          const Text('Possible repetition detected — consider regenerating.'),
      ],
    ]);
  }
}
