import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/today/week_item_type.dart';
import 'package:personal_secretary/today/week_overlap.dart';
import 'package:personal_secretary/today/week_today_column.dart';
import 'package:personal_secretary/ui/object_bookmark.dart';

void main() {
  WeekOverlapSpan span(String id, DateTime start, DateTime end) {
    return WeekOverlapSpan(id: id, start: start, end: end);
  }

  DateTime t(int hour, [int minute = 0, int day = 8]) {
    return DateTime(2026, 9, day, hour, minute);
  }

  test('isolated event is depth 0', () {
    final depths = weekOverlapDepths([span('solo', t(10), t(11))]);
    expect(depths['solo'], 0);
  });

  test('nested second event is depth 1', () {
    final depths = weekOverlapDepths([
      span('a', t(10), t(18)),
      span('b', t(13), t(14)),
    ]);
    expect(depths['a'], 0);
    expect(depths['b'], 1);
  });

  test('third nested event is depth 2', () {
    final depths = weekOverlapDepths([
      span('a', t(10), t(18)),
      span('b', t(11), t(16)),
      span('c', t(12), t(14)),
    ]);
    expect(depths['a'], 0);
    expect(depths['b'], 1);
    expect(depths['c'], 2);
  });

  test('fourth and deeper presentation clamp to 3', () {
    final depths = weekOverlapDepths([
      span('a', t(10), t(18)),
      span('b', t(11), t(16)),
      span('c', t(12), t(14)),
      span('d', t(12, 30), t(13, 30)),
      span('e', t(12, 40), t(13, 10)),
    ]);
    expect(depths['a'], 0);
    expect(depths['b'], 1);
    expect(depths['c'], 2);
    expect(depths['d'], 3);
    expect(depths['e'], 3);
    expect(weekOverlapClampDepth(9), 3);
  });

  test('non-overlapping adjacent events stay at depth 0', () {
    final depths = weekOverlapDepths([
      span('a', t(9), t(10)),
      span('b', t(10), t(11)),
    ]);
    expect(depths['a'], 0);
    expect(depths['b'], 0);
  });

  test('depths are independent of input order', () {
    final events = [
      span('c', t(12), t(14)),
      span('a', t(10), t(18)),
      span('b', t(11), t(16)),
    ];
    final forward = weekOverlapDepths(events);
    final reversed = weekOverlapDepths(events.reversed);
    expect(reversed, forward);
    expect(forward['a'], 0);
    expect(forward['b'], 1);
    expect(forward['c'], 2);
  });

  test('multi-day depth is day-local', () {
    final overnight = span('night', t(23, 0, 7), t(2, 0, 8));
    final tuesdayMorning = span('morning', t(1, 0, 8), t(3, 0, 8));
    final monday = weekOverlapDepths([
      span('night', overnight.start, DateTime(2026, 9, 8)),
    ]);
    final tuesday = weekOverlapDepths([
      span('night', DateTime(2026, 9, 8), overnight.end),
      tuesdayMorning,
    ]);
    expect(monday['night'], 0);
    expect(tuesday['night'], isNotNull);
    expect(tuesday['morning'], isNotNull);
    expect({tuesday['night'], tuesday['morning']}, {0, 1});
  });

  test('inset and width factors match the dense cascade', () {
    expect(weekOverlapLeftInset(0), 0.00);
    expect(weekOverlapLeftInset(1), 0.04);
    expect(weekOverlapLeftInset(2), 0.07);
    expect(weekOverlapLeftInset(3), 0.10);
    expect(weekOverlapLeftInset(8), 0.10);
    expect(weekOverlapWidthFactor(0), 1.00);
    expect(weekOverlapWidthFactor(1), closeTo(0.96, 0.001));
    expect(weekOverlapWidthFactor(2), closeTo(0.93, 0.001));
    expect(weekOverlapWidthFactor(3), closeTo(0.90, 0.001));
  });

  test('depth tones are distinguishable and theme-aware', () {
    void checkScheme(ColorScheme scheme) {
      final tones = [
        for (var depth = 0; depth <= 4; depth++) weekOverlapTone(scheme, depth),
      ];
      expect(tones[0].fill, isNot(tones[1].fill));
      expect(tones[1].fill, isNot(tones[2].fill));
      expect(tones[2].fill, isNot(tones[3].fill));
      expect(tones[3].fill, tones[4].fill);
      for (final tone in tones.take(4)) {
        expect(tone.foreground, isNot(tone.fill));
        expect(
          weekOverlapContrastRatio(tone.fill, tone.foreground),
          greaterThan(4.5),
        );
      }
      final bookmark = bookmarkTokenColor('blue', scheme);
      for (final tone in tones.take(4)) {
        expect(tone.fill, isNot(bookmark));
        expect(tone.foreground, isNot(bookmark));
      }
    }

    checkScheme(ColorScheme.fromSeed(seedColor: const Color(0xFF1565C0)));
    checkScheme(
      ColorScheme.fromSeed(
        seedColor: const Color(0xFF1565C0),
        brightness: Brightness.dark,
      ),
    );
  });

  test('wide title style is denser than phone', () {
    const theme = TextTheme(labelSmall: TextStyle(fontSize: 11, height: 1.3));
    final wide = weekEventTitleStyle(
      theme,
      color: Colors.black,
      compact: false,
    );
    final phone = weekEventTitleStyle(
      theme,
      color: Colors.black,
      compact: true,
    );
    expect(wide.fontSize, kWeekWideEventTitleSize);
    expect(wide.height, kWeekWideEventTitleHeight);
    expect(phone.fontSize, 11);
    expect(phone.fontSize, greaterThan(wide.fontSize!));
  });

  test('calendar commitment maps to outlined calendar icon', () {
    expect(
      weekTemporalItemTypeIcon(WeekTemporalItemType.calendarCommitment),
      Icons.calendar_today_outlined,
    );
    expect(
      weekTemporalItemTypeSemantics(WeekTemporalItemType.calendarCommitment),
      'Календарное событие',
    );
    expect(kWeekWideTypeGlyphSize, 13);
    expect(kWeekPhoneTypeGlyphSize, 13.5);
    expect(kWeekWideTypeGlyphSize, greaterThan(kWeekWideProviderGlyphSize));
    expect(kWeekPhoneTypeGlyphSize, greaterThan(kWeekPhoneProviderGlyphSize));
    expect(kWeekIdentityRailGap, 2);
  });

  test('today column tint is distinct from surface in light and dark', () {
    void check(ColorScheme scheme) {
      final tint = weekTodayColumnColor(scheme);
      expect(tint, isNot(scheme.surface));
      expect(
        (tint.computeLuminance() - scheme.surface.computeLuminance()).abs(),
        greaterThan(0.004),
      );
    }

    check(ColorScheme.fromSeed(seedColor: const Color(0xFF1565C0)));
    check(
      ColorScheme.fromSeed(
        seedColor: const Color(0xFF1565C0),
        brightness: Brightness.dark,
      ),
    );
  });
}
