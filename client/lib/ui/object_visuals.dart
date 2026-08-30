import 'package:flutter/material.dart';

export 'domain_labels.dart' show objectKindLabel;

const Map<String, String> _providerLabels = {
  'gmail': 'Gmail',
  'yandex_mail': 'Яндекс',
  'local_device': 'Компьютер',
  'upload': 'Загрузка',
  'web': 'Веб',
  'google': 'Google',
  'google_calendar': 'Google Календарь',
  'yandex': 'Яндекс',
  'calendar': 'Календарь',
  'outlook': 'Outlook',
  'microsoft': 'Microsoft',
  'telegram': 'Telegram',
  'slack': 'Slack',
};

const Map<String, String> _providerBadgeGlyphs = {
  'gmail': 'G',
  'yandex_mail': 'Я',
  'local_device': 'ПК',
  'upload': '↑',
  'web': 'W',
};

IconData iconForKind(String kind) {
  switch (kind) {
    case 'task':
      return Icons.task_alt_outlined;
    case 'email':
      return Icons.email_outlined;
    case 'event':
    case 'calendar_event':
      return Icons.event_outlined;
    case 'file':
      return Icons.insert_drive_file_outlined;
    case 'document':
      return Icons.description_outlined;
    case 'dataset':
      return Icons.table_chart_outlined;
    case 'note':
      return Icons.sticky_note_2_outlined;
    case 'chat':
    case 'message':
      return Icons.chat_bubble_outline;
    case 'project':
      return Icons.folder_outlined;
    default:
      return Icons.category_outlined;
  }
}

String providerLabel(String? provider) {
  if (provider == null || provider.trim().isEmpty) {
    return '';
  }
  final normalized = provider.trim().toLowerCase();
  return _providerLabels[normalized] ?? provider;
}

Widget providerBadge(BuildContext context, String? provider) {
  if (provider == null || provider.trim().isEmpty) {
    return const SizedBox.shrink();
  }
  final normalized = provider.trim().toLowerCase();
  final glyph = _providerBadgeGlyphs[normalized];
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
