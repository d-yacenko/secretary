import 'package:flutter/material.dart';

import 'object_presentation.dart';

export 'object_presentation.dart'
    show iconForKind, objectKindLabel, providerLabel, providerCompactGlyph;

Widget providerBadge(BuildContext context, String? provider) {
  if (provider == null || provider.trim().isEmpty) {
    return const SizedBox.shrink();
  }
  final glyph = providerCompactGlyph(provider);
  final label = providerLabel(provider);
  final scheme = Theme.of(context).colorScheme;
  final child = glyph != null
      ? Text(
          glyph,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                fontWeight: FontWeight.w600,
              ),
        )
      : Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: Theme.of(context).textTheme.labelSmall,
        );
  return Container(
    padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
    decoration: BoxDecoration(
      color: scheme.surfaceContainerHighest,
      borderRadius: BorderRadius.circular(4),
      border: Border.all(color: scheme.outlineVariant),
    ),
    child: child,
  );
}
