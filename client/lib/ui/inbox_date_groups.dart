import 'package:flutter/material.dart';

import '../api/api_models.dart';
import 'date_format.dart';

DateTime? parseLocalInboxDate(String? iso) {
  if (iso == null || iso.trim().isEmpty) {
    return null;
  }
  final parsed = DateTime.tryParse(iso);
  if (parsed == null) {
    return null;
  }
  final local = parsed.toLocal();
  return DateTime(local.year, local.month, local.day);
}

bool isWeekendDate(DateTime date) {
  return date.weekday == DateTime.saturday || date.weekday == DateTime.sunday;
}

String formatInboxDateSeparator(DateTime date) {
  return '${formatRussianDayMonth(date, padDay: true)} · ${formatRussianWeekday(date)}';
}

sealed class InboxSourceListEntry {
  const InboxSourceListEntry();
}

class InboxDateSeparatorEntry extends InboxSourceListEntry {
  const InboxDateSeparatorEntry({required this.date, required this.label});

  final DateTime? date;
  final String label;

  bool get isWeekend => date != null && isWeekendDate(date!);
}

class InboxSourceObjectEntry extends InboxSourceListEntry {
  const InboxSourceObjectEntry(this.sourceObject);

  final InboxSourceObjectOut sourceObject;
}

/// Inserts date separators into an already-ordered list without re-sorting.
List<InboxSourceListEntry> groupInboxSourceEntries(
  List<InboxSourceObjectOut> objects,
) {
  final entries = <InboxSourceListEntry>[];
  DateTime? currentDate;
  var undatedOpen = false;
  for (final object in objects) {
    final date = parseLocalInboxDate(object.feedStamp);
    if (date == null) {
      if (!undatedOpen) {
        entries.add(
          const InboxDateSeparatorEntry(date: null, label: 'Без даты'),
        );
        undatedOpen = true;
        currentDate = null;
      }
      entries.add(InboxSourceObjectEntry(object));
      continue;
    }
    undatedOpen = false;
    if (currentDate != date) {
      currentDate = date;
      entries.add(
        InboxDateSeparatorEntry(
          date: date,
          label: formatInboxDateSeparator(date),
        ),
      );
    }
    entries.add(InboxSourceObjectEntry(object));
  }
  return entries;
}

class InboxDateSeparator extends StatelessWidget {
  const InboxDateSeparator({super.key, required this.entry});

  final InboxDateSeparatorEntry entry;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final style = Theme.of(context).textTheme.titleSmall?.copyWith(
          color: entry.isWeekend ? scheme.error : scheme.primary,
          fontWeight: FontWeight.w700,
        );
    return Padding(
      padding: const EdgeInsets.fromLTRB(0, 8, 0, 4),
      child: Row(
        children: [
          Flexible(
            child: Text(
              entry.label,
              style: style,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Divider(
              height: 1,
              thickness: 1,
              color: scheme.outlineVariant,
            ),
          ),
        ],
      ),
    );
  }
}
