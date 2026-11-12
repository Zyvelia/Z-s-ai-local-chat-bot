import 'design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'main.dart';

// Community views are isolated from the v0.1-v0.6 chat and character editor.
class DiscoveryScreen extends StatefulWidget {
  final Api api;
  final Future<void> Function(Map<String, dynamic>) onOpen;
  const DiscoveryScreen({super.key, required this.api, required this.onOpen});
  @override
  State<DiscoveryScreen> createState() => _DiscoveryScreenState();
}
class _DiscoveryScreenState extends State<DiscoveryScreen> {
  final search = TextEditingController();
  String tag = '', sort = 'trending';
  int offset = 0, total = 0;
  List<dynamic> items = [];
  bool loading = false;
  String? loadError;
  @override
  void initState() { super.initState(); load(); }
  @override
  void dispose() { search.dispose(); super.dispose(); }
  Future<void> load({bool reset = false}) async {
    if (reset) offset = 0;
    setState(() => loading = true);
    try {
      final response = await widget.api.discover(query: search.text.trim(), tag: tag, sort: sort, offset: offset);
      if (mounted) setState(() { items = response['items'] as List; total = response['total'] as int; loadError = null; });
    } catch (e) { if (mounted) setState(() => loadError = e.toString()); }
    finally { if (mounted) setState(() => loading = false); }
  }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Discover characters')),
    body: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 1180),
      child: ListView(padding: const EdgeInsets.all(16), children: [
        TextField(controller: search, onSubmitted: (_) => load(reset: true), maxLength: 120,
          decoration: InputDecoration(labelText: 'Search names, descriptions and tags', suffixIcon: IconButton(
            icon: const Icon(Icons.search), onPressed: () => load(reset: true)))),
        Wrap(spacing: 10, runSpacing: 8, children: [
          SizedBox(width: 190, child: TextField(decoration: const InputDecoration(labelText: 'Tag / category'),
            onChanged: (v) => tag = v.trim().toLowerCase(), onSubmitted: (_) => load(reset: true))),
          DropdownButton<String>(value: sort, items: const [
            DropdownMenuItem(value: 'trending', child: Text('Trending')),
            DropdownMenuItem(value: 'popular', child: Text('Popular')),
            DropdownMenuItem(value: 'newest', child: Text('Newest')),
            DropdownMenuItem(value: 'rating', child: Text('Top rated')),
          ], onChanged: (v) { if (v != null) { sort = v; load(reset: true); } }),
          OutlinedButton.icon(onPressed: () => load(reset: true), icon: const Icon(Icons.filter_alt_outlined), label: const Text('Apply')),
        ]),
        if (loading) const LinearProgressIndicator(),
        if (loadError != null) RetryView(message: loadError!, onRetry: () => load(reset: true)),
        SectionTitle('Explore characters', subtitle: '$total public characters'),
        if (!loading && items.isEmpty) const EmptyView(icon: Icons.search_off_outlined,
          title: 'No characters found', message: 'Try a different name, tag, or category.'),
        LayoutBuilder(builder: (context, box) => GridView.builder(
          shrinkWrap: true, physics: const NeverScrollableScrollPhysics(),
          itemCount: items.length, gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: AppLayout.gridColumns(box.maxWidth), mainAxisExtent: 175,
            crossAxisSpacing: 8, mainAxisSpacing: 8), itemBuilder: (context, i) {
              final c = Map<String, dynamic>.from(items[i] as Map);
              return CharacterTile(key: ValueKey('result-${c['id']}'), character: c, onTap: () => widget.onOpen(c));
            })),
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          TextButton(onPressed: offset == 0 || loading ? null : () { offset = (offset - 20).clamp(0, total); load(); }, child: const Text('Previous')),
          Text('${offset + 1}–${(offset + items.length).clamp(0, total)} of $total'),
          TextButton(onPressed: offset + items.length >= total || loading ? null : () { offset += 20; load(); }, child: const Text('Next')),
        ]),
      ]))),
  );
}

class CharacterCommunityPanel extends StatefulWidget {
  final Api api;
  final String characterId, creatorId;
  final bool isPublic;
  final VoidCallback onOpenCreator;
  const CharacterCommunityPanel({super.key, required this.api, required this.characterId,
    required this.creatorId, required this.isPublic, required this.onOpenCreator});
  @override
  State<CharacterCommunityPanel> createState() => _CharacterCommunityPanelState();
}
class _CharacterCommunityPanelState extends State<CharacterCommunityPanel> {
  Map<String, dynamic>? stats;
  @override
  void initState() { super.initState(); load(); }
  Future<void> load() async {
    try { final result = await widget.api.characterCommunity(widget.characterId); if (mounted) setState(() => stats = result); }
    catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> chooseCollection() async {
    try {
      final collections = await widget.api.collections();
      if (!mounted) return;
      final id = await showDialog<String>(context: context, builder: (ctx) => SimpleDialog(title: const Text('Add to collection'),
        children: collections.map((c) => SimpleDialogOption(onPressed: () => Navigator.pop(ctx, c['id']), child: Text(c['title'] as String))).toList()));
      if (id != null) { await widget.api.addToCollection(id, widget.characterId); if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Saved to collection'))); }
    } catch (e) { if (mounted) showError(context, e); }
  }
  Future<void> report() async {
    String reason = 'spam'; final details = TextEditingController();
    try {
      final confirmed = await showDialog<bool>(context: context, builder: (ctx) => StatefulBuilder(builder: (ctx, update) => AlertDialog(
        title: const Text('Report character'), content: Column(mainAxisSize: MainAxisSize.min, children: [
          DropdownButton<String>(value: reason, isExpanded: true, items: const [
            DropdownMenuItem(value: 'spam', child: Text('Spam')),
            DropdownMenuItem(value: 'harassment', child: Text('Harassment')),
            DropdownMenuItem(value: 'sexual_content', child: Text('Sexual content')),
            DropdownMenuItem(value: 'violence', child: Text('Violence')),
            DropdownMenuItem(value: 'impersonation', child: Text('Impersonation')),
            DropdownMenuItem(value: 'other', child: Text('Other')),
          ], onChanged: (v) => update(() => reason = v ?? reason)),
          TextField(controller: details, maxLength: 1000, maxLines: 3, decoration: const InputDecoration(labelText: 'Details')),
        ]), actions: [TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Submit'))])));
      if (confirmed == true) {
        await widget.api.reportCharacter(widget.characterId, reason, details.text);
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Report submitted')));
      }
    } catch (e) { if (mounted) showError(context, e); }
    finally { details.dispose(); }
  }
  Future<void> share() async {
    // PUBLIC_WEB_URL should be configured to a deployed origin when launched.
    const configured = String.fromEnvironment('PUBLIC_WEB_URL', defaultValue: '');
    final origin = configured.isNotEmpty ? configured : Uri.base.hasScheme && Uri.base.host.isNotEmpty ? Uri.base.origin : '';
    if (origin.isEmpty || stats?['share_path'] == null) {
      if (mounted) showError(context, 'Set PUBLIC_WEB_URL to the hosted website URL before sharing links');
      return;
    }
    await Clipboard.setData(ClipboardData(text: '$origin${stats!['share_path']}'));
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Link copied')));
  }
  @override
  Widget build(BuildContext context) {
    final s = stats;
    if (s == null) return const LinearProgressIndicator();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Community · ${s['favorites']} favorites · ★ ${s['average_rating'] ?? '—'} (${s['rating_count']} ratings)'),
      Wrap(spacing: 8, children: [
        OutlinedButton.icon(onPressed: () async { try { await widget.api.setFavorite(widget.characterId, s['favorite'] != true); await load(); } catch (e) { if (mounted) showError(context, e); } },
          icon: Icon(s['favorite'] == true ? Icons.favorite : Icons.favorite_border), label: Text(s['favorite'] == true ? 'Unfavorite' : 'Favorite')),
        OutlinedButton.icon(onPressed: chooseCollection, icon: const Icon(Icons.library_add_outlined), label: const Text('Collect')),
        OutlinedButton.icon(onPressed: widget.onOpenCreator, icon: const Icon(Icons.person_outline), label: const Text('Creator')),
        if (widget.isPublic) OutlinedButton.icon(onPressed: share, icon: const Icon(Icons.share_outlined), label: const Text('Share')),
        if (widget.isPublic) OutlinedButton.icon(onPressed: report, icon: const Icon(Icons.flag_outlined), label: const Text('Report')),
      ]),
      if (widget.isPublic) Wrap(spacing: 4, children: List.generate(5, (i) => IconButton(
        tooltip: 'Rate ${i+1} stars', icon: Icon((s['my_rating'] ?? 0) > i ? Icons.star : Icons.star_outline),
        onPressed: () async { try { await widget.api.rateCharacter(widget.characterId, i + 1); await load(); } catch (e) { if (mounted) showError(context, e); } },
      ))),
    ]);
  }
}

class CreatorScreen extends StatefulWidget {
  final Api api;
  final String? creatorId;
  final bool own;
  final Future<void> Function(Map<String, dynamic>) onOpen;
  const CreatorScreen({super.key, required this.api, this.creatorId, this.own = false, required this.onOpen});
  @override
  State<CreatorScreen> createState() => _CreatorScreenState();
}
class _CreatorScreenState extends State<CreatorScreen> {
  Map<String, dynamic>? profile;
  List<dynamic> characters = [];
  bool loading = true;
  @override
  void initState() { super.initState(); load(); }
  Future<void> load() async {
    try {
      final id = widget.creatorId ?? (await widget.api.request('GET', '/users/me'))['id'] as String;
      final p = await widget.api.creator(id);
      final chars = await widget.api.creatorCharacters(id);
      if (mounted) setState(() { profile = p; characters = chars['items'] as List; loading = false; });
    } catch (e) { if (mounted) { setState(() => loading = false); showError(context, e); } }
  }
  Future<void> edit() async {
    final handle = TextEditingController(text: profile?['handle'] ?? '');
    final bio = TextEditingController(text: profile?['bio'] ?? '');
    final avatar = TextEditingController(text: profile?['avatar_url'] ?? '');
    try {
      final save = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(title: const Text('Edit creator profile'),
        content: SizedBox(width: 460, child: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: handle, decoration: const InputDecoration(labelText: 'Unique handle')),
          TextField(controller: bio, decoration: const InputDecoration(labelText: 'Biography'), maxLength: 1000, maxLines: 3),
          TextField(controller: avatar, decoration: const InputDecoration(labelText: 'Avatar HTTPS URL')),
        ])), actions: [TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save'))]));
      if (save == true) { await widget.api.saveCreator({'handle': handle.text.trim(), 'bio': bio.text.trim(), 'avatar_url': avatar.text.trim()}); await load(); }
    } catch (e) { if (mounted) showError(context, e); }
    finally { handle.dispose(); bio.dispose(); avatar.dispose(); }
  }
  @override
  Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Creator profile')),
    body: loading ? const Center(child: CircularProgressIndicator()) : profile == null ? const Center(child: Text('Creator unavailable'))
      : ListView(padding: const EdgeInsets.all(20), children: [
        if ((profile!['avatar_url'] as String? ?? '').startsWith('https://'))
          CircleAvatar(radius: 35, foregroundImage: NetworkImage(profile!['avatar_url'] as String)),
        Text(profile!['display_name'] ?? '', style: Theme.of(context).textTheme.headlineMedium),
        Text('@${profile!['handle'] ?? ''}'),
        Text(profile!['bio'] ?? ''),
        Text('${profile!['follower_count']} followers'),
        if (widget.own) OutlinedButton(onPressed: edit, child: const Text('Edit public profile')),
        if (!widget.own) FilledButton(onPressed: () async { try { await widget.api.followCreator(profile!['user_id'], profile!['is_following'] != true); await load(); } catch (e) { if (mounted) showError(context, e); } },
          child: Text(profile!['is_following'] == true ? 'Unfollow creator' : 'Follow creator')),
        const SizedBox(height: 15),
        Text('Public characters', style: Theme.of(context).textTheme.titleLarge),
        ...characters.map((item) => ListTile(title: Text(item['name'] ?? ''), subtitle: Text(item['tagline'] ?? ''),
            onTap: () => widget.onOpen(Map<String, dynamic>.from(item as Map)))),
      ]));
}

class LibraryScreen extends StatefulWidget {
  final Api api;
  final Future<void> Function(Map<String, dynamic>) onOpen;
  const LibraryScreen({super.key, required this.api, required this.onOpen});
  @override
  State<LibraryScreen> createState() => _LibraryScreenState();
}
class _LibraryScreenState extends State<LibraryScreen> {
  List<dynamic> favorites = [], collections = [];
  Map<String, List<dynamic>> items = {};
  bool busy = true;
  @override
  void initState() { super.initState(); load(); }
  Future<void> load() async {
    try {
      final f = await widget.api.favorites();
      final c = await widget.api.collections();
      final result = <String, List<dynamic>>{};
      for (final item in c) { result[item['id'] as String] = await widget.api.collectionItems(item['id'] as String); }
      if (mounted) setState(() { favorites = f; collections = c; items = result; busy = false; });
    } catch (e) { if (mounted) { setState(() => busy = false); showError(context, e); } }
  }
  Future<void> create() async {
    final name = TextEditingController(); final desc = TextEditingController();
    try {
      final save = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(title: const Text('New collection'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: name, maxLength: 100, decoration: const InputDecoration(labelText: 'Title')),
          TextField(controller: desc, maxLength: 400, decoration: const InputDecoration(labelText: 'Description')),
        ]), actions: [TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Create'))]));
      if (save == true) { await widget.api.addCollection(name.text.trim(), desc.text.trim()); await load(); }
    } catch (e) { if (mounted) showError(context, e); }
    finally { name.dispose(); desc.dispose(); }
  }
  @override
  Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('My library'), actions: [
    IconButton(onPressed: create, tooltip: 'New collection', icon: const Icon(Icons.create_new_folder_outlined)),
  ]), body: busy ? const Center(child: CircularProgressIndicator()) : ListView(padding: const EdgeInsets.all(16), children: [
    Text('Favorites', style: Theme.of(context).textTheme.titleLarge),
    ...favorites.map((c) => ListTile(title: Text(c['name'] ?? ''),
      trailing: IconButton(icon: const Icon(Icons.favorite), tooltip: 'Remove favorite', onPressed: () async {
        try { await widget.api.setFavorite(c['id'] as String, false); await load(); } catch (e) { if (mounted) showError(context, e); }
      }), onTap: () => widget.onOpen(Map<String, dynamic>.from(c as Map)))),
    const Divider(), Text('Collections', style: Theme.of(context).textTheme.titleLarge),
    ...collections.map((c) => ExpansionTile(title: Text(c['title'] ?? ''), subtitle: Text(c['description'] ?? ''), children: [
      ...?items[c['id']]?.map((item) => ListTile(title: Text(item['name'] ?? ''), onTap: () => widget.onOpen(Map<String, dynamic>.from(item as Map)),
        trailing: IconButton(tooltip: 'Remove from collection', icon: const Icon(Icons.remove_circle_outline), onPressed: () async {
          try { await widget.api.removeFromCollection(c['id'], item['id']); await load(); } catch (e) { if (mounted) showError(context, e); }
        }))),
      TextButton.icon(onPressed: () async { try { await widget.api.deleteCollection(c['id']); await load(); } catch (e) { if (mounted) showError(context, e); } },
        icon: const Icon(Icons.delete_outline), label: const Text('Delete collection')),
    ])),
  ]));
}
