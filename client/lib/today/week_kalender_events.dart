import 'package:flutter/material.dart';
import 'package:kalender/kalender.dart';

import '../api/api_models.dart';
import 'week_item_type.dart';

/// Calendar event bound to a Secretary Object.id.
class SecretaryWeekEvent extends CalendarEvent {
  SecretaryWeekEvent({
    required String objectId,
    required super.dateTimeRange,
    required this.title,
    this.provider,
    this.itemType = WeekTemporalItemType.calendarCommitment,
    super.isAllDay = false,
  }) : super(id: objectId, interaction: EventInteraction.allowNone());

  final String title;
  final String? provider;
  final WeekTemporalItemType itemType;

  String get objectId => id;

  @override
  SecretaryWeekEvent copyWithData({required DateTimeRange dateTimeRange}) {
    return SecretaryWeekEvent(
      objectId: id,
      dateTimeRange: dateTimeRange,
      title: title,
      provider: provider,
      itemType: itemType,
      isAllDay: isAllDay,
    );
  }

  @override
  bool operator ==(Object other) {
    return super == other &&
        other is SecretaryWeekEvent &&
        other.title == title &&
        other.provider == provider &&
        other.itemType == itemType;
  }

  @override
  int get hashCode => Object.hash(super.hashCode, title, provider, itemType);
}

/// Deterministic rendered-projection identity for Week layout updates.
///
/// Covers week identity, today metadata, and layout-relevant event fields.
/// Unrelated Object metadata is omitted so equivalent snapshots do not relayout.
String weekPresentationSignature(WeekOut week) {
  final buffer = StringBuffer()
    ..write(week.weekStart)
    ..write('|')
    ..write(week.weekEnd)
    ..write('|')
    ..write(week.todayDate)
    ..write('|')
    ..write(week.isCurrentWeek);
  for (final day in week.days) {
    buffer
      ..write('|')
      ..write(day.date)
      ..write(':');
    for (final event in day.events) {
      final object = event.object;
      buffer
        ..write(object.id)
        ..write('\t')
        ..write(object.title)
        ..write('\t')
        ..write(object.provider ?? '')
        ..write('\t')
        ..write(object.startAt ?? '')
        ..write('\t')
        ..write(object.dueAt ?? '')
        ..write('\t')
        ..write(event.allDay)
        ..write(';');
    }
  }
  return buffer.toString();
}

/// Unique events from a Week projection, using original start/end instants.
///
/// The backend repeats an Object on every overlapping local day. Kalender must
/// receive each Object once so it can place overnight and multi-day spans.
List<SecretaryWeekEvent> weekOutToKalenderEvents(WeekOut week) {
  final first = <String, WeekEvent>{};
  final allDay = <String, bool>{};
  for (final day in week.days) {
    for (final event in day.events) {
      final id = event.object.id;
      first.putIfAbsent(id, () => event);
      allDay[id] = (allDay[id] ?? false) || event.allDay;
    }
  }
  final events = <SecretaryWeekEvent>[];
  for (final entry in first.entries) {
    final event = entry.value;
    final start = DateTime.tryParse(event.object.startAt ?? '');
    if (start == null) {
      continue;
    }
    var end = DateTime.tryParse(event.object.dueAt ?? '');
    if (end == null || !end.isAfter(start)) {
      end = start.add(const Duration(minutes: 30));
    }
    events.add(
      SecretaryWeekEvent(
        objectId: entry.key,
        dateTimeRange: DateTimeRange(start: start, end: end),
        title: event.object.title,
        provider: event.object.provider,
        itemType: WeekTemporalItemType.calendarCommitment,
        isAllDay: allDay[entry.key] ?? false,
      ),
    );
  }
  return events;
}
