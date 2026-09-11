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

const double kWeekTodayColumnTintAlpha = 0.05;

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
                return Row(
                  children: [
                    for (var i = 0; i < 7; i++)
                      Expanded(
                        child: i == todayIndex
                            ? ColoredBox(
                                key: const Key('week_today_column_highlight'),
                                color: scheme.primary.withValues(
                                  alpha: kWeekTodayColumnTintAlpha,
                                ),
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
