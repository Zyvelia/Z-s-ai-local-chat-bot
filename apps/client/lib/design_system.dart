import 'package:flutter/material.dart';

/// Shared layout rules for mobile, tablet and desktop/web window sizes.
class AppLayout {
  static const double tablet = 700;
  static const double desktop = 1080;
  static const double contentMax = 1260;
  static bool isWide(double width) => width >= desktop;
  static bool isTablet(double width) => width >= tablet;
  static int gridColumns(double width) => width >= 1200 ? 4 : width >= 850 ? 3 : width >= 520 ? 2 : 1;
}

class AppThemes {
  static const accent = Color(0xff9885ff);
  static ThemeData build(Brightness mode) {
    final dark = mode == Brightness.dark;
    final scheme = ColorScheme.fromSeed(seedColor: accent, brightness: mode,
      surface: dark ? const Color(0xff11121c) : const Color(0xfffaf9ff));
    return ThemeData(
      useMaterial3: true, colorScheme: scheme, scaffoldBackgroundColor: scheme.surface,
      visualDensity: VisualDensity.standard,
      appBarTheme: AppBarTheme(backgroundColor: scheme.surface, centerTitle: false),
      cardTheme: CardThemeData(elevation: 0,
        color: dark ? const Color(0xff1c1d2b) : const Color(0xfff0eff9),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20))),
      inputDecorationTheme: InputDecorationTheme(
        filled: true, fillColor: dark ? const Color(0xff222332) : const Color(0xfff0eff8),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none)),
      filledButtonTheme: FilledButtonThemeData(style: FilledButton.styleFrom(
        minimumSize: const Size(48, 48), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)))),
    );
  }
}

class PageFrame extends StatelessWidget {
  final Widget child;
  final double maxWidth;
  final EdgeInsetsGeometry padding;
  const PageFrame({super.key, required this.child, this.maxWidth = AppLayout.contentMax,
    this.padding = const EdgeInsets.symmetric(horizontal: 20, vertical: 20)});
  @override Widget build(BuildContext context) => Center(child: ConstrainedBox(
    constraints: BoxConstraints(maxWidth: maxWidth),
    child: Padding(padding: padding, child: child)));
}

class SectionTitle extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget? action;
  const SectionTitle(this.title, {super.key, this.subtitle, this.action});
  @override Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Row(children: [Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
      children: [Text(title, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
        if (subtitle != null) Text(subtitle!, style: Theme.of(context).textTheme.bodySmall)])),
      if (action != null) action!]));
}

class CharacterTile extends StatelessWidget {
  final Map<String, dynamic> character;
  final VoidCallback onTap;
  const CharacterTile({super.key, required this.character, required this.onTap});
  @override Widget build(BuildContext context) {
    final name = character['name']?.toString() ?? 'Unnamed character';
    final tags = (character['tags'] as List? ?? const []).take(2).join(' · ');
    return Card(clipBehavior: Clip.antiAlias, child: InkWell(
      onTap: onTap,
      child: Padding(padding: const EdgeInsets.all(16), child: Column(
        crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
          Row(children: [CircleAvatar(radius: 25, child: Text(name.isNotEmpty ? name.substring(0, 1).toUpperCase() : '?')),
            const Spacer(), const Icon(Icons.arrow_outward, size: 18)]),
          const SizedBox(height: 15),
          Text(name, maxLines: 1, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 5),
          Text(character['tagline']?.toString() ?? 'Start a new story', maxLines: 2, overflow: TextOverflow.ellipsis),
          const SizedBox(height: 12),
          if (tags.isNotEmpty) Text(tags, maxLines: 1, style: Theme.of(context).textTheme.labelSmall),
        ])),
    ));
  }
}

class EmptyView extends StatelessWidget {
  final IconData icon;
  final String title;
  final String message;
  final Widget? action;
  const EmptyView({super.key, required this.icon, required this.title, required this.message, this.action});
  @override Widget build(BuildContext context) => Center(child: Padding(padding: const EdgeInsets.all(28),
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(icon, size: 48, color: Theme.of(context).colorScheme.primary),
      const SizedBox(height: 14), Text(title, style: Theme.of(context).textTheme.titleLarge),
      const SizedBox(height: 6), Text(message, textAlign: TextAlign.center),
      if (action != null) ...[const SizedBox(height: 14), action!],
    ])));
}

class RetryView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const RetryView({super.key, required this.message, required this.onRetry});
  @override Widget build(BuildContext context) => EmptyView(
    icon: Icons.wifi_off_outlined, title: 'Something went wrong', message: message,
    action: FilledButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh), label: const Text('Try again')));
}

class LoadingView extends StatelessWidget {
  final String label;
  const LoadingView({super.key, this.label = 'Loading…'});
  @override Widget build(BuildContext context) => Center(child: Semantics(liveRegion: true,
    label: label, child: Column(mainAxisSize: MainAxisSize.min, children: [
      const CircularProgressIndicator(), const SizedBox(height: 12), Text(label)])));
}

class ChatBubble extends StatelessWidget {
  final String content;
  final bool isUser;
  final String? speaker;
  final Widget? actions;
  const ChatBubble({super.key, required this.content, required this.isUser, this.speaker, this.actions});
  @override Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Align(alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 660),
        child: Card(color: isUser ? scheme.primaryContainer : null, child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            if (speaker != null) ...[Text(speaker!, style: Theme.of(context).textTheme.labelMedium?.copyWith(fontWeight: FontWeight.bold)), const SizedBox(height: 5)],
            RoleplayText(content: content),
            if (actions != null) actions!,
          ])))));
  }
}


/// Rich, selectable text for *actions*, **emphasis** and spoken dialogue.
/// This only styles locally; it never interprets HTML or executes markup.
class RoleplayText extends StatelessWidget {
  final String content;
  const RoleplayText({super.key, required this.content});

  static List<TextSpan> spans(String source, Color actionColor) {
    final parts = <TextSpan>[];
    final pattern = RegExp(r'(\*\*[^*\n]+\*\*|\*[^*\n]+\*)');
    var cursor = 0;
    for (final match in pattern.allMatches(source)) {
      if (match.start > cursor) parts.add(TextSpan(text: source.substring(cursor, match.start)));
      final part = match.group(0)!;
      if (part.startsWith('**')) {
        parts.add(TextSpan(text: part.substring(2, part.length - 2), style: const TextStyle(fontWeight: FontWeight.bold)));
      } else {
        parts.add(TextSpan(text: part.substring(1, part.length - 1), style: TextStyle(fontStyle: FontStyle.italic, color: actionColor)));
      }
      cursor = match.end;
    }
    if (cursor < source.length) parts.add(TextSpan(text: source.substring(cursor)));
    return parts;
  }

  @override Widget build(BuildContext context) => SelectableText.rich(
    TextSpan(style: DefaultTextStyle.of(context).style,
      children: spans(content, Theme.of(context).colorScheme.secondary)));
}
