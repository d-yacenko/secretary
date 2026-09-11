import 'package:flutter/material.dart';
import 'package:kalender/kalender.dart';

import '../api/api_models.dart';

/// Monday–Sunday index of today in [week], or null when no body highlight.
int? weekTodayColumnIndex(WeekOut week) {
  if (!week.isCurrentWeek) {
    return null;
  }
  final index = week.days.indexWhere((day) => day.date == week.todayDate);
  if (index < 0 || index > 6) {
    return null;
  }
  return index;
}

const double kWeekTodayColumnTintAlpha = 0.085;
const double kWeekTodayBadgeSize = 26;

/// Theme-aware full-column Today tint. Distinct from bare [ColorScheme.surface].
Color weekTodayColumnColor(ColorScheme scheme) {
  return Color.alphaBlend(
    scheme.primary.withValues(alpha: kWeekTodayColumnTintAlpha),
    scheme.surface,
  );
}

/// Saturated Today date-badge fill. Independent of provider, overlap, bookmark.
///
/// App primary (indigo seed) is too muted/lavender for a Google-like date
/// circle, so this uses a local semantic blue still split by theme brightness.
Color weekTodayBadgeFill(ColorScheme scheme) {
  return scheme.brightness == Brightness.dark
      ? const Color(0xFF90CAF9)
      : const Color(0xFF1565C0);
}

Color weekTodayBadgeForeground(ColorScheme scheme) {
  return scheme.brightness == Brightness.dark
      ? const Color(0xFF0D47A1)
      : const Color(0xFFFFFFFF);
}

/// Hour-lines layer with a restrained today-column tint behind the lines.
///
/// Public kalender API only: custom [HourLinesBuilder] + [HourLines].
class WeekTodayColumnHourLines extends StatelessWidget {
  const WeekTodayColumnHourLines({
    super.key,
    required this.todayIndex,
    required this.heightPerMinute,
    required this.timeOfDayRange,
  });

  final int? todayIndex;
  final double heightPerMinute;
  final TimeOfDayRange timeOfDayRange;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        if (todayIndex != null)
          Positioned.fill(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final scheme = Theme.of(context).colorScheme;
                final tint = weekTodayColumnColor(scheme);
                return Row(
                  children: [
                    for (var i = 0; i < 7; i++)
                      Expanded(
                        child: i == todayIndex
                            ? ColoredBox(
                                key: const Key('week_today_column_highlight'),
                                color: tint,
                              )
                            : const SizedBox.expand(),
                      ),
                  ],
                );
              },
            ),
          ),
        HourLines(
          heightPerMinute: heightPerMinute,
          timeOfDayRange: timeOfDayRange,
        ),
      ],
    );
  }
}
