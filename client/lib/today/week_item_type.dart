import 'package:flutter/material.dart';

/// Semantic temporal kind occupying the Week time map.
///
/// Independent of source provider (Google / Yandex) and of bookmark color.
enum WeekTemporalItemType {
  /// Confirmed provider calendar event. The only kind `/week` currently returns.
  calendarCommitment,
}

const double kWeekWideTypeGlyphSize = 9.5;
const double kWeekPhoneTypeGlyphSize = 10.5;

IconData weekTemporalItemTypeIcon(WeekTemporalItemType type) {
  switch (type) {
    case WeekTemporalItemType.calendarCommitment:
      return Icons.calendar_today_outlined;
  }
}

String weekTemporalItemTypeSemantics(WeekTemporalItemType type) {
  switch (type) {
    case WeekTemporalItemType.calendarCommitment:
      return 'Календарное событие';
  }
}

Key weekTemporalItemTypeKey(WeekTemporalItemType type, String objectId) {
  switch (type) {
    case WeekTemporalItemType.calendarCommitment:
      return Key('week_type_calendar_$objectId');
  }
}

/// Display-only type glyph. Does not handle taps or API calls.
class WeekTemporalItemTypeGlyph extends StatelessWidget {
  const WeekTemporalItemTypeGlyph({
    super.key,
    required this.objectId,
    required this.itemType,
    required this.size,
    required this.color,
  });

  final String objectId;
  final WeekTemporalItemType itemType;
  final double size;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Semantics(
        label: weekTemporalItemTypeSemantics(itemType),
        child: Icon(
          key: weekTemporalItemTypeKey(itemType, objectId),
          weekTemporalItemTypeIcon(itemType),
          size: size,
          color: color,
        ),
      ),
    );
  }
}
