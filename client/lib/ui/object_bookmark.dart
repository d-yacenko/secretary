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

class ObjectBookmarkRibbon extends StatelessWidget {
  const ObjectBookmarkRibbon({
    super.key,
    required this.child,
    this.color,
    this.onTapTab,
  });

  final Widget child;
  final String? color;
  final VoidCallback? onTapTab;

  @override
  Widget build(BuildContext context) {
    if (color == null) {
      return child;
    }
    final tokenColor = bookmarkTokenColor(color!, Theme.of(context).colorScheme);
    return Stack(
      clipBehavior: Clip.none,
      children: [
        child,
        Positioned(
          top: 0,
          right: 10,
          child: GestureDetector(
            onTap: onTapTab,
            child: Container(
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
            ),
          ),
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
    return PopupMenuButton<String>(
      key: const Key('object_bookmark_control'),
      tooltip: 'Закладка',
      padding: EdgeInsets.zero,
      onSelected: (value) {
        if (value == '__clear__') {
          onClear();
          return;
        }
        onSelect(value);
      },
      itemBuilder: (context) => [
        for (final token in kBookmarkColorTokens)
          PopupMenuItem(
            value: token,
            child: Row(
              children: [
                Container(
                  width: 12,
                  height: 12,
                  decoration: BoxDecoration(
                    color: bookmarkTokenColor(token, Theme.of(context).colorScheme),
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
            value: '__clear__',
            child: Text('Убрать закладку'),
          ),
      ],
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
