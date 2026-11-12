import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:character_chat_client/sse_parser.dart';

void main() {
  test('SSE parses split frames, comments, and CRLF', () async {
    final chunks = <String>[
      ': keep alive\r\nevent: token\r\ndata: {"text":"Hel',
      'lo"}\r\n\r\nevent: done\r\ndata: {"saved":true}\r\n\r\n',
    ];
    final events = await decodeChatEvents(Stream.fromIterable(chunks.map(utf8.encode))).toList();
    expect(events, [
      {'event': 'token', 'text': 'Hello'},
      {'event': 'done', 'saved': true},
    ]);
  });

  test('SSE supports multi-line JSON data and final event', () async {
    final text = 'event: token\ndata: {\ndata: "text": "world"}\n\nevent: error\ndata: {"message":"offline"}';
    final events = await decodeChatEvents(Stream.value(utf8.encode(text))).toList();
    expect(events[0]['text'], 'world');
    expect(events[1], {'event': 'error', 'message': 'offline'});
  });

  test('SSE rejects malformed response payload', () async {
    expect(decodeChatEvents(Stream.value(utf8.encode('data: not-json\n\n'))).toList(), throwsFormatException);
  });
}
