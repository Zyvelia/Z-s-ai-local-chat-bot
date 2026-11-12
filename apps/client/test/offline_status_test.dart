import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:character_chat_client/offline_status_ui.dart';

void main() {
  testWidgets('offline banner describes cache and provides sync action', (tester) async {
    var synced = false;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: OfflineSyncStatus(
      offline: true, pending: 2, conflicts: 0, onSync: () => synced = true, onReview: () {}))));
    expect(find.textContaining('Offline. Showing locally saved content'), findsOneWidget);
    await tester.tap(find.text('Sync now'));
    expect(synced, isTrue);
  });
  testWidgets('conflict banner requires explicit review', (tester) async {
    var reviewed = false;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: OfflineSyncStatus(
      offline: false, pending: 1, conflicts: 1, onSync: () {}, onReview: () => reviewed = true))));
    expect(find.textContaining('need review'), findsOneWidget);
    await tester.tap(find.text('Review conflicts'));
    expect(reviewed, isTrue);
  });
  testWidgets('synced state stays out of the way', (tester) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: OfflineSyncStatus(
      offline: false, pending: 0, conflicts: 0, onSync: () {}, onReview: () {}))));
    expect(find.byType(MaterialBanner), findsNothing);
  });
}
