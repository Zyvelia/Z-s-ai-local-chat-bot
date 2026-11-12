import 'package:flutter/material.dart';

/// Display sync state without confusing local edits with server acknowledgements.
class OfflineSyncStatus extends StatelessWidget {
  final bool offline;
  final int pending;
  final int conflicts;
  final VoidCallback onSync;
  final VoidCallback onReview;
  const OfflineSyncStatus({super.key, required this.offline, required this.pending,
    required this.conflicts, required this.onSync, required this.onReview});

  @override
  Widget build(BuildContext context) {
    if (!offline && pending == 0) return const SizedBox.shrink();
    return Semantics(label: offline ? 'Offline: saved chats available' : 'Online: synchronizing changes',
      child: MaterialBanner(content: Text(conflicts > 0
        ? '$conflicts offline edit conflict${conflicts == 1 ? '' : 's'} need review.'
        : offline ? 'Offline. Showing locally saved content. $pending edit(s) queued.'
        : '$pending edit(s) waiting to sync.'),
        leading: Icon(conflicts > 0 ? Icons.warning_amber_outlined : offline ? Icons.cloud_off_outlined : Icons.sync_outlined),
        actions: [
          if (conflicts > 0) TextButton(onPressed: onReview, child: const Text('Review conflicts')),
          TextButton(onPressed: onSync, child: const Text('Sync now')),
        ]));
  }
}
