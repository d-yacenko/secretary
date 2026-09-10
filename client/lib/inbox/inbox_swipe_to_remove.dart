import 'package:flutter/material.dart';

/// Target swipe distance before a release can activate Remove.
///
/// A fraction of card width is derived from this so a phone (~360px) and a
/// tablet (~800px) both need a deliberate horizontal swipe, without requiring
/// a ~40% drag across a wide tablet card.
const double kInboxSwipeRemoveExtentPx = 96;

const double kInboxSwipeRemoveMinFraction = 0.18;
const double kInboxSwipeRemoveMaxFraction = 0.4;

double inboxSwipeRemoveDismissThreshold(double cardWidth) {
  if (cardWidth <= 0) {
    return kInboxSwipeRemoveMaxFraction;
  }
  return (kInboxSwipeRemoveExtentPx / cardWidth).clamp(
    kInboxSwipeRemoveMinFraction,
    kInboxSwipeRemoveMaxFraction,
  );
}

class InboxSwipeRemoveBackground extends StatelessWidget {
  const InboxSwipeRemoveBackground({super.key, required this.objectId});

  final String objectId;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return ColoredBox(
      key: Key('inbox_swipe_remove_background_$objectId'),
      color: scheme.error,
      child: Align(
        alignment: Alignment.centerRight,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.delete_outline,
                color: scheme.onError,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                'Удалить',
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: scheme.onError,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Touch-only end-to-start swipe that reveals Remove and gates dismissal on
/// the existing confirmation + successful DELETE.
class InboxSwipeToRemove extends StatelessWidget {
  const InboxSwipeToRemove({
    super.key,
    required this.objectId,
    required this.onConfirmRemove,
    required this.onRemoved,
    required this.child,
  });

  final String objectId;
  final Future<bool> Function() onConfirmRemove;
  final VoidCallback onRemoved;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth.isFinite && constraints.maxWidth > 0
            ? constraints.maxWidth
            : MediaQuery.sizeOf(context).width;
        return Dismissible(
          key: Key('inbox_swipe_remove_$objectId'),
          direction: DismissDirection.endToStart,
          dismissThresholds: {
            DismissDirection.endToStart:
                inboxSwipeRemoveDismissThreshold(width),
          },
          confirmDismiss: (direction) async {
            if (direction != DismissDirection.endToStart) {
              return false;
            }
            return onConfirmRemove();
          },
          onDismissed: (_) => onRemoved(),
          background: InboxSwipeRemoveBackground(objectId: objectId),
          child: child,
        );
      },
    );
  }
}
