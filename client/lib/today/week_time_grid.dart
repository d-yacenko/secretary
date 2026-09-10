import 'package:flutter/material.dart';
import 'package:kalender/kalender.dart';

import '../api/api_models.dart';
import '../ui/app_spacing.dart';
import '../ui/date_format.dart';
import '../ui/object_bookmark.dart';
import '../ui/object_bookmark_controller.dart';
import '../ui/object_presentation.dart';
import 'week_kalender_events.dart';

final _readOnlyInteraction = CalendarInteraction(
  allowResizing: false,
  allowRescheduling: false,
  allowEventCreation: false,
);

/// Read-only week time-grid over [WeekOut], backed by kalender.
class WeekTimeGrid extends StatefulWidget {
  const WeekTimeGrid({
    super.key,
    required this.week,
    required this.onOpen,
    required this.bookmarks,
    this.onRequestWeekStart,
    this.now,
  });

  final WeekOut week;
  final ValueChanged<String> onOpen;
  final ValueChanged<String>? onRequestWeekStart;
  final DateTime Function()? now;
  final ObjectBookmarkController bookmarks;

  @override
  State<WeekTimeGrid> createState() => _WeekTimeGridState();
}

class _WeekTimeGridState extends State<WeekTimeGrid> {
  final _events = DefaultEventsController();
  final _calendar = CalendarController();
  late DateTime Function() _now;
  ViewConfiguration? _viewConfiguration;

  @override
  void initState() {
    super.initState();
    _now = widget.now ?? DateTime.now;
    widget.bookmarks.addListener(_onBookmarksChanged);
    _events.replaceEvents(weekOutToKalenderEvents(widget.week));
  }

  @override
  void didUpdateWidget(covariant WeekTimeGrid oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.bookmarks != widget.bookmarks) {
      oldWidget.bookmarks.removeListener(_onBookmarksChanged);
      widget.bookmarks.addListener(_onBookmarksChanged);
    }
    _now = widget.now ?? DateTime.now;
    _events.replaceEvents(weekOutToKalenderEvents(widget.week));
    if (oldWidget.week.weekStart != widget.week.weekStart) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!_calendar.isAttached) {
          return;
        }
        _calendar.jumpToDate(_civilLocal(widget.week.weekStart));
      });
    }
  }

  @override
  void dispose() {
    widget.bookmarks.removeListener(_onBookmarksChanged);
    _calendar.dispose();
    _events.dispose();
    super.dispose();
  }

  void _onBookmarksChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  DateTime _civilLocal(String iso) {
    final civil = parseCalendarDate(iso);
    return DateTime(civil.year, civil.month, civil.day);
  }

  ViewConfiguration _buildViewConfiguration() {
    final initial = _civilLocal(widget.week.weekStart);
    final now = _now();
    final initialTime = widget.week.isCurrentWeek
        ? TimeOfDay(hour: now.hour, minute: now.minute)
        : const TimeOfDay(hour: 8, minute: 0);
    final compact = MediaQuery.sizeOf(context).width < AppSpacing.wideBreakpoint;
    if (compact) {
      return MultiDayViewConfiguration.singleDay(
        initialDateTime: initial,
        initialTimeOfDay: initialTime,
        initialHeightPerMinute: 0.9,
        nowCallback: _now,
      );
    }
    return MultiDayViewConfiguration.week(
      initialDateTime: initial,
      firstDayOfWeek: DateTime.monday,
      initialTimeOfDay: initialTime,
      initialHeightPerMinute: 0.9,
      nowCallback: _now,
    );
  }

  void _onPageChanged(DateTimeRange range) {
    final onRequest = widget.onRequestWeekStart;
    if (onRequest == null) {
      return;
    }
    final civil = parseCalendarDate(formatCalendarDate(range.start));
    final monday = addCalendarDays(civil, 1 - civil.weekday);
    final iso = formatCalendarDate(monday);
    if (iso != widget.week.weekStart) {
      onRequest(iso);
    }
  }

  @override
  Widget build(BuildContext context) {
    final compact =
        MediaQuery.sizeOf(context).width < AppSpacing.wideBreakpoint;
    _viewConfiguration = _buildViewConfiguration();
    final empty = widget.week.days.every((day) => day.events.isEmpty);
    final tiles = TileComponents(tileBuilder: _tileBuilder);
    return Column(
      children: [
        if (empty)
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text('На этой неделе событий нет'),
            ),
          ),
        Expanded(
          child: KalenderView(
            key: const Key('week_time_grid'),
            eventsController: _events,
            calendarController: _calendar,
            viewConfiguration: _viewConfiguration!,
            locale: const Locale('ru'),
            callbacks: CalendarCallbacks(
              onEventTapped: (event) => widget.onOpen(event.id),
              onPageChanged: _onPageChanged,
            ),
            components: CalendarComponents(
              multiDayComponents: MultiDayComponents(
                headerComponents: MultiDayHeaderComponents(
                  dayHeaderBuilder: (context, date) => _WeekDayHeader(
                    date: date,
                    todayDate: widget.week.todayDate,
                  ),
                ),
              ),
            ),
            header: CalendarHeader(
              interaction: _readOnlyInteraction,
              multiDayTileComponents: tiles,
            ),
            body: CalendarBody(
              interaction: _readOnlyInteraction,
              multiDayBodyConfiguration: MultiDayBodyConfiguration(
                eventLayoutStrategy: EventLayoutStrategy.overlap(),
                pageScrollPhysics: compact
                    ? null
                    : const NeverScrollableScrollPhysics(),
              ),
              multiDayTileComponents: tiles,
            ),
          ),
        ),
      ],
    );
  }

  Widget _tileBuilder(
    BuildContext context,
    CalendarEvent event,
    DateTimeRange tileRange,
  ) {
    final secretary = event is SecretaryWeekEvent ? event : null;
    final dayIso = formatCalendarDate(tileRange.start);
    return WeekKalenderEventTile(
      key: Key('week_event_${dayIso}_${event.id}'),
      objectId: event.id,
      title: secretary?.title ?? '',
      provider: secretary?.provider,
      allDay: event.isAllDay,
      bookmarkColor: widget.bookmarks.colorFor(event.id),
    );
  }
}

class _WeekDayHeader extends StatelessWidget {
  const _WeekDayHeader({
    required this.date,
    required this.todayDate,
  });

  final DateTime date;
  final String todayDate;

  @override
  Widget build(BuildContext context) {
    final iso = formatCalendarDate(date);
    final isToday = iso == todayDate;
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      key: Key('week_day_$iso'),
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
      child: Text(
        key: Key(isToday ? 'week_day_today_$iso' : 'week_day_header_$iso'),
        '${formatRussianWeekdayShort(date)} ${formatRussianDayMonth(date)}',
        textAlign: TextAlign.center,
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: isToday ? scheme.primary : null,
              fontWeight: isToday ? FontWeight.w600 : FontWeight.w500,
            ),
      ),
    );
  }
}

class WeekKalenderEventTile extends StatelessWidget {
  const WeekKalenderEventTile({
    super.key,
    required this.objectId,
    required this.title,
    required this.provider,
    required this.allDay,
    this.bookmarkColor,
  });

  final String objectId;
  final String title;
  final String? provider;
  final bool allDay;
  final String? bookmarkColor;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final glyph = compactProviderGlyphWidget(provider, size: 11);
    final tokenColor = bookmarkColor == null
        ? null
        : bookmarkTokenColor(bookmarkColor!, scheme);
    return Material(
      color: scheme.primaryContainer.withValues(alpha: 0.78),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(4),
        side: BorderSide(
          color: scheme.outline.withValues(alpha: 0.42),
          width: 0.8,
        ),
      ),
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 2, 4, 2),
            child: Row(
              children: [
                if (glyph != null) ...[
                  glyph,
                  const SizedBox(width: 4),
                ],
                Expanded(
                  child: Text(
                    title,
                    maxLines: allDay ? 1 : 3,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: scheme.onPrimaryContainer,
                        ),
                  ),
                ),
                if (allDay)
                  Padding(
                    padding: const EdgeInsets.only(left: 4),
                    child: Text(
                      'Весь день',
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color:
                                scheme.onPrimaryContainer.withValues(alpha: 0.8),
                          ),
                    ),
                  ),
              ],
            ),
          ),
          if (tokenColor != null)
            Positioned(
              top: 0,
              right: 0,
              child: IgnorePointer(
                child: ObjectBookmarkGlyph(
                  key: Key('week_bookmark_$objectId'),
                  fillColor: tokenColor,
                  size: kBookmarkTabSize,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
