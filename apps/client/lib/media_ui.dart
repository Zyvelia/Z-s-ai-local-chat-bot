import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';

/// Authenticated media requests are supplied by the API client; no public file URL is needed.
class PrivateMediaImage extends StatelessWidget {
  final dynamic api;
  final String mediaId;
  final double? width;
  final double? height;
  final BoxFit fit;
  const PrivateMediaImage({super.key, required this.api, required this.mediaId, this.width, this.height, this.fit = BoxFit.cover});
  @override
  Widget build(BuildContext context) => FutureBuilder<Uint8List>(
    future: api.mediaBytes(mediaId) as Future<Uint8List>,
    builder: (context, snapshot) {
      if (!snapshot.hasData) return SizedBox(width: width, height: height, child: const Center(child: Icon(Icons.image_outlined)));
      return Image.memory(snapshot.data!, width: width, height: height, fit: fit,
        errorBuilder: (_, __, ___) => const Icon(Icons.broken_image_outlined));
    });
}

class MediaManagerScreen extends StatefulWidget {
  final dynamic api;
  final String scope;
  final String scopeId;
  final bool canEdit;
  const MediaManagerScreen({super.key, required this.api, required this.scope, required this.scopeId, this.canEdit = false});
  @override State<MediaManagerScreen> createState() => _MediaManagerScreenState();
}

class _MediaManagerScreenState extends State<MediaManagerScreen> {
  List<dynamic> items = [];
  bool busy = false;
  String? error;
  @override void initState() { super.initState(); refresh(); }
  Future<void> refresh() async {
    try {
      final result = await widget.api.mediaList(widget.scope, widget.scopeId);
      if (mounted) setState(() { items = result; error = null; });
    } catch (e) { if (mounted) setState(() => error = e.toString()); }
  }
  Future<void> add(String purpose) async {
    final picked = await FilePicker.platform.pickFiles(type: FileType.custom, allowedExtensions: ['jpg','jpeg','png','webp'], withData: true);
    if (picked == null || picked.files.isEmpty) return;
    final file = picked.files.single;
    if (file.bytes == null || file.bytes!.length > 5 * 1024 * 1024) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Choose an image under 5 MiB')));
      return;
    }
    setState(() => busy = true);
    try { await widget.api.uploadMedia(widget.scope, widget.scopeId, purpose, file.name, file.bytes!); await refresh(); }
    catch (e) { if (mounted) setState(() => error = e.toString()); }
    finally { if (mounted) setState(() => busy = false); }
  }
  Future<void> remove(String id) async {
    setState(() => busy = true);
    try { await widget.api.removeMedia(id); await refresh(); }
    catch (e) { if (mounted) setState(() => error = e.toString()); }
    finally { if (mounted) setState(() => busy = false); }
  }
  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Media library')),
    body: ListView(padding: const EdgeInsets.all(16), children: [
      if (error != null) ListTile(title: Text(error!), trailing: IconButton(onPressed: refresh, icon: const Icon(Icons.refresh))),
      if (widget.canEdit) Wrap(spacing: 8, children: [
        if (widget.scope != 'conversation') FilledButton.icon(onPressed: busy ? null : () => add('avatar'), icon: const Icon(Icons.account_circle_outlined), label: const Text('Upload avatar')),
        if (widget.scope == 'character') OutlinedButton.icon(onPressed: busy ? null : () => add('gallery'), icon: const Icon(Icons.add_photo_alternate_outlined), label: const Text('Add gallery image')),
        if (widget.scope == 'conversation') FilledButton.icon(onPressed: busy ? null : () => add('background'), icon: const Icon(Icons.wallpaper_outlined), label: const Text('Set chat background')),
      ]),
      if (busy) const LinearProgressIndicator(),
      if (items.isEmpty) const Padding(padding: EdgeInsets.all(28), child: Text('No images uploaded yet.')),
      ...items.map((item) {
        final m = Map<String,dynamic>.from(item as Map);
        return Card(child: ListTile(
          leading: ClipRRect(borderRadius: BorderRadius.circular(8), child: PrivateMediaImage(api: widget.api, mediaId: m['id'] as String, width: 64, height: 64)),
          title: Text(m['purpose']?.toString() ?? 'Image'),
          subtitle: Text('${((m['size_bytes'] as num? ?? 0) / 1024).round()} KiB'),
          trailing: widget.canEdit ? IconButton(tooltip: 'Delete image', onPressed: busy ? null : () => remove(m['id'] as String), icon: const Icon(Icons.delete_outline)) : null,
        ));
      }),
    ]),
  );
}
