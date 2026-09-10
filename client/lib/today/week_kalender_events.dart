import 'package:flutter/material.dart';
import 'package:kalender/kalender.dart';

import '../api/api_models.dart';

/// Calendar event bound to a Secretary Object.id.
class SecretaryWeekEvent extends CalendarEvent {
  SecretaryWeekEvent({
    required String objectId,
    required super.dateTimeRange,
    required this.title,
    this.provider,
    super.isAllDay = false,
  }) : super(
          id: objectId,
          interaction: EventInteraction.allowNone(),
        );

  final String title;
  final String? provider;

  String get objectId => id;

  @override
  SecretaryWeekEvent copyWithData({required DateTimeRange dateTimeRange}) {
    return SecretaryWeekEvent(
      objectId: id,
      dateTimeRange: dateTimeRange,
      title: title,
      provider: provider,
    );
  }

  @override
  bool operator ==(Object other) {
    return super == other &&
        other is SecretaryWeekEvent &&
        other.title == title &&
        other.provider == provider;
  }

  @override
  int get hashCode => Object.hash(super.hashCode, title, provider);
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
        isAllDay: allDay[entry.key] ?? false,
      ),
    );
  }
  return events;
}
