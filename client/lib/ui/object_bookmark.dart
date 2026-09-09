import 'package:flutter/material.dart';

const List<String> kBookmarkColorTokens = [
  'red',
  'orange',
  'yellow',
  'green',
  'blue',
  'violet',
  'gray',
];

const String kBookmarkClearMenuValue = '__clear__';

Color bookmarkTokenColor(String token, ColorScheme scheme) {
  switch (token) {
    case 'red':
      return const Color(0xFFE53935);
    case 'orange':
      return const Color(0xFFFB8C00);
    case 'yellow':
      return const Color(0xFFFDD835);
    case 'green':
      return const Color(0xFF43A047);
    case 'blue':
      return const Color(0xFF1E88E5);
    case 'violet':
      return const Color(0xFF8E24AA);
    case 'gray':
      return scheme.outline;
    default:
      return scheme.outline;
  }
}

List<PopupMenuEntry<String>> bookmarkPaletteEntries({
  required String? color,
  required ColorScheme scheme,
}) {
  return [
    for (final token in kBookmarkColorTokens)
      PopupMenuItem(
        value: token,
        child: Row(
          children: [
            Container(
              width: 12,
              height: 12,
              decoration: BoxDecoration(
                color: bookmarkTokenColor(token, scheme),
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 8),
            Text(token),
          ],
        ),
      ),
    if (color != null)
      const PopupMenuItem(
        value: kBookmarkClearMenuValue,
        child: Text('Убрать закладку'),
      ),
  ];
}

void handleBookmarkMenuSelection(
  String value, {
  required ValueChanged<String> onSelect,
  required VoidCallback onClear,
}) {
  if (value == kBookmarkClearMenuValue) {
    onClear();
    return;
  }
  onSelect(value);
}

class ObjectBookmarkPaletteButton extends StatelessWidget {
  const ObjectBookmarkPaletteButton({
    super.key,
    required this.color,
    required this.onSelect,
    required this.onClear,
    required this.child,
    this.tooltip = 'Закладка',
    this.padding = EdgeInsets.zero,
  });

  final String? color;
  final ValueChanged<String> onSelect;
  final VoidCallback onClear;
  final Widget child;
  final String tooltip;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<String>(
      tooltip: tooltip,
      padding: padding,
      onSelected: (value) => handleBookmarkMenuSelection(
        value,
        onSelect: onSelect,
        onClear: onClear,
      ),
      itemBuilder: (context) => bookmarkPaletteEntries(
        color: color,
        scheme: Theme.of(context).colorScheme,
      ),
      child: child,
    );
  }
}

class ObjectBookmarkRibbon extends StatelessWidget {
  const ObjectBookmarkRibbon({
    super.key,
    required this.child,
    this.color,
    this.onSelect,
    this.onClear,
  });

  final Widget child;
  final String? color;
  final ValueChanged<String>? onSelect;
  final VoidCallback? onClear;

  @override
  Widget build(BuildContext context) {
    if (color == null) {
      return child;
    }
    final tokenColor = bookmarkTokenColor(color!, Theme.of(context).colorScheme);
    final tab = Container(
      key: const Key('object_bookmark_tab'),
      width: 10,
      height: 18,
      decoration: BoxDecoration(
        color: tokenColor,
        borderRadius: const BorderRadius.only(
          bottomLeft: Radius.circular(2),
          bottomRight: Radius.circular(2),
        ),
      ),
    );
    final canEdit = onSelect != null && onClear != null;
    return Stack(
      clipBehavior: Clip.none,
      children: [
        child,
        Positioned(
          top: 0,
          right: 10,
          child: canEdit
              ? ObjectBookmarkPaletteButton(
                  color: color,
                  onSelect: onSelect!,
                  onClear: onClear!,
                  child: tab,
                )
              : tab,
        ),
      ],
    );
  }
}

class ObjectBookmarkControl extends StatelessWidget {
  const ObjectBookmarkControl({
    super.key,
    required this.color,
    required this.onSelect,
    required this.onClear,
  });

  final String? color;
  final ValueChanged<String> onSelect;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    return ObjectBookmarkPaletteButton(
      key: const Key('object_bookmark_control'),
      color: color,
      onSelect: onSelect,
      onClear: onClear,
      child: Icon(
        color == null ? Icons.bookmark_border : Icons.bookmark,
        size: 18,
        color: color == null
            ? Theme.of(context).colorScheme.onSurfaceVariant
            : bookmarkTokenColor(color!, Theme.of(context).colorScheme),
      ),
    );
  }
}
