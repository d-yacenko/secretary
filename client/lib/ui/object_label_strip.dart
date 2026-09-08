import 'package:flutter/material.dart';

import '../api/api_models.dart';
import 'app_spacing.dart';

class ObjectLabelStrip extends StatelessWidget {
  const ObjectLabelStrip({
    super.key,
    required this.labels,
    this.maxVisible = 2,
  });

  final List<LabelItem> labels;
  final int maxVisible;

  @override
  Widget build(BuildContext context) {
    if (labels.isEmpty) {
      return const SizedBox.shrink();
    }
    final visible = labels.take(maxVisible).toList();
    final overflow = labels.length - visible.length;
    final scheme = Theme.of(context).colorScheme;
    final style = Theme.of(context).textTheme.labelSmall?.copyWith(
          color: scheme.onSurfaceVariant,
          fontWeight: FontWeight.w500,
        );
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.xs),
      child: Wrap(
        spacing: AppSpacing.xs,
        runSpacing: AppSpacing.xs,
        children: [
          for (final label in visible)
            Tooltip(
              message: _tooltip(label),
              child: Semantics(
                label: _tooltip(label),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 160),
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      color: scheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(color: scheme.outlineVariant),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.sm,
                        vertical: 2,
                      ),
                      child: Text(
                        label.title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: style,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          if (overflow > 0)
            Tooltip(
              message: labels.skip(maxVisible).map((e) => e.title).join(', '),
              child: Semantics(
                label: '+$overflow',
                child: DecoratedBox(
                  key: const Key('object_label_overflow'),
                  decoration: BoxDecoration(
                    color: scheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: scheme.outlineVariant),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.sm,
                      vertical: 2,
                    ),
                    child: Text('+$overflow', style: style),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  String _tooltip(LabelItem label) {
    final description = label.description?.trim();
    if (description == null || description.isEmpty) {
      return label.title;
    }
    return '${label.title}\n$description';
  }
}
