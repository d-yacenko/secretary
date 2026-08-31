import 'package:flutter/material.dart';

/// Shared kind/provider presentation for Search, Graph filters, and cards.

const Map<String, String> objectKindLabels = {
  'task': 'Задача',
  'email': 'Письмо',
  'calendar_event': 'Событие',
  'event': 'Событие',
  'project': 'Проект',
  'note': 'Заметка',
  'file': 'Файл',
  'folder': 'Папка',
  'document': 'Документ',
  'dataset': 'Таблица',
  'chat': 'Чат',
  'message': 'Сообщение',
  'chat_message': 'Сообщение',
};

const Map<String, String> providerLabels = {
  'gmail': 'Gmail',
  'yandex_mail': 'Яндекс',
  'local_device': 'Компьютер',
  'upload': 'Загрузка',
  'web': 'Веб',
  'google': 'Google',
  'google_calendar': 'Google Календарь',
  'google_drive': 'Google Диск',
  'yandex': 'Яндекс',
  'yandex_calendar': 'Яндекс Календарь',
  'yandex_disk': 'Яндекс.Диск',
  'calendar': 'Календарь',
  'outlook': 'Outlook',
  'microsoft': 'Microsoft',
  'telegram': 'Telegram',
  'slack': 'Slack',
  'mattermost': 'Mattermost',
};

const Map<String, String> providerCompactGlyphs = {
  'gmail': 'G',
  'google_calendar': 'G',
  'yandex_mail': 'Я',
  'yandex_calendar': 'Я',
  'local_device': 'ПК',
  'upload': '↑',
  'web': 'W',
  'google_drive': 'G',
  'yandex_disk': 'Я',
  'mattermost': 'M',
};

String objectKindLabel(String kind) =>
    objectKindLabels[kind] ?? kind;

String providerLabel(String? provider) {
  if (provider == null || provider.isEmpty) {
    return 'Источник';
  }
  return providerLabels[provider] ?? provider;
}

String? providerCompactGlyph(String? provider) {
  if (provider == null || provider.isEmpty) {
    return null;
  }
  return providerCompactGlyphs[provider];
}

IconData iconForObjectKind(String kind) {
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
    case 'folder':
      return Icons.folder_outlined;
    case 'chat':
    case 'message':
    case 'chat_message':
      return Icons.chat_bubble_outline;
    case 'project':
      return Icons.work_outline;
    default:
      return Icons.category_outlined;
  }
}

IconData iconForKind(String kind) => iconForObjectKind(kind);

/// Compact provider glyph for header rows; null when provider is absent.
Widget? compactProviderGlyphWidget(String? provider, {double size = 14}) {
  if (provider == null || provider.isEmpty) {
    return null;
  }
  final glyph = providerCompactGlyph(provider);
  if (glyph != null) {
    return Text(
      glyph,
      style: TextStyle(fontSize: size, fontWeight: FontWeight.w600),
    );
  }
  return Icon(Icons.storage_outlined, size: size);
}

Widget providerCompactIcon(String? provider, {double size = 18}) {
  final glyphWidget = compactProviderGlyphWidget(provider, size: size);
  if (glyphWidget != null) {
    return glyphWidget;
  }
  return Icon(Icons.storage_outlined, size: size);
}

/// Compact title + kind icon + provider glyph + trailing metadata on one row.
class ObjectCompactHeaderRow extends StatelessWidget {
  const ObjectCompactHeaderRow({
    super.key,
    required this.title,
    required this.kind,
    this.provider,
    required this.trailingText,
    this.trailingBadges = const [],
    this.semanticsLabel,
  });

  final String title;
  final String kind;
  final String? provider;
  final String trailingText;
  final List<Widget> trailingBadges;
  final String? semanticsLabel;

  @override
  Widget build(BuildContext context) {
    final kindLabel = objectKindLabel(kind);
    final providerName = providerLabel(provider);
    final label = semanticsLabel ?? '$kindLabel, $providerName';
    final titleStyle = Theme.of(context).textTheme.titleMedium?.copyWith(
          fontWeight: FontWeight.w600,
        );
    final metadataStyle = Theme.of(context).textTheme.bodyMedium;
    final providerGlyph = compactProviderGlyphWidget(provider, size: 14);

    return Semantics(
      label: label,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            child: Text(
              title,
              style: titleStyle,
              overflow: TextOverflow.ellipsis,
              maxLines: 2,
            ),
          ),
          const SizedBox(width: 12),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(iconForKind(kind), size: 16),
              if (providerGlyph != null) ...[
                const SizedBox(width: 6),
                providerGlyph,
              ],
              ...trailingBadges.map(
                (badge) => Padding(
                  padding: const EdgeInsets.only(left: 6),
                  child: badge,
                ),
              ),
              if (trailingText.isNotEmpty) ...[
                const SizedBox(width: 6),
                Text('·', style: metadataStyle),
                const SizedBox(width: 6),
                Text(
                  trailingText,
                  style: metadataStyle,
                  overflow: TextOverflow.ellipsis,
                  maxLines: 2,
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}
