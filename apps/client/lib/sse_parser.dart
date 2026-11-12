import 'dart:convert';

/// Decode SSE frames independently of network chunk boundaries. Supports
/// multi-line data, comments, CRLF, and the final unterminated event.
Stream<Map<String, dynamic>> decodeChatEvents(Stream<List<int>> body) async* {
  var currentEvent = 'message';
  final dataLines = <String>[];
  final lines = body.transform(utf8.decoder).transform(const LineSplitter());

  Map<String, dynamic>? flush() {
    if (dataLines.isEmpty) {
      currentEvent = 'message';
      return null;
    }
    final text = dataLines.join('\n');
    final event = currentEvent;
    currentEvent = 'message';
    dataLines.clear();
    final decoded = jsonDecode(text);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Invalid SSE JSON object');
    }
    return {'event': event, ...decoded};
  }

  await for (final line in lines) {
    if (line.isEmpty) {
      final result = flush();
      if (result != null) yield result;
      continue;
    }
    if (line.startsWith(':')) continue;
    final separator = line.indexOf(':');
    final field = separator == -1 ? line : line.substring(0, separator);
    var value = separator == -1 ? '' : line.substring(separator + 1);
    if (value.startsWith(' ')) value = value.substring(1);
    switch (field) {
      case 'event': currentEvent = value; break;
      case 'data': dataLines.add(value); break;
    }
  }
  final finalEvent = flush();
  if (finalEvent != null) yield finalEvent;
}
