import 'package:flutter/material.dart';
import 'package:kalender/kalender.dart';

import '../api/api_models.dart';
import '../ui/app_spacing.dart';
import '../ui/date_format.dart';
import '../ui/object_bookmark.dart';
import '../ui/object_bookmark_controller.dart';
import '../ui/object_presentation.dart';
import 'week_kalender_events.dart';
import 'week_item_type.dart';
import 'week_overlap.dart';
import 'week_overlap_layout.dart';
import 'week_today_column.dart';

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
  ViewConfiguration? _viewConfiguration;
  String? _eventsSignature;
  String? _configWeekStart;
  bool? _configCompact;
  bool? _configCurrentWeek;

  DateTime _nowCallback() => (widget.now ?? DateTime.now)();

  @override
  void initState() {
    super.initState();
    widget.bookmarks.addListener(_onBookmarksChanged);
    _eventsSignature = weekPresentationSignature(widget.week);
    _events.replaceEvents(weekOutToKalenderEvents(widget.week));
  }

  @override
  void didUpdateWidget(covariant WeekTimeGrid oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.bookmarks != widget.bookmarks) {
      oldWidget.bookmarks.removeListener(_onBookmarksChanged);
      widget.bookmarks.addListener(_onBookmarksChanged);
    }
    final nextSignature = weekPresentationSignature(widget.week);
    if (nextSignature != _eventsSignature) {
      _eventsSignature = nextSignature;
      _events.replaceEvents(weekOutToKalenderEvents(widget.week));
    }
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

  ViewConfiguration _buildViewConfiguration({
    required bool compact,
    required TimeOfDay initialTime,
  }) {
    final initial = _civilLocal(widget.week.weekStart);
    if (compact) {
      return MultiDayViewConfiguration.singleDay(
        initialDateTime: initial,
        initialTimeOfDay: initialTime,
        initialHeightPerMinute: 0.9,
        nowCallback: _nowCallback,
      );
    }
    return MultiDayViewConfiguration.week(
      initialDateTime: initial,
      firstDayOfWeek: DateTime.monday,
      initialTimeOfDay: initialTime,
      initialHeightPerMinute: 0.9,
      nowCallback: _nowCallback,
    );
  }

  void _syncViewConfiguration({required bool compact}) {
    final weekStart = widget.week.weekStart;
    final isCurrent = widget.week.isCurrentWeek;
    if (_viewConfiguration != null &&
        _configWeekStart == weekStart &&
        _configCompact == compact &&
        _configCurrentWeek == isCurrent) {
      return;
    }
    final now = _nowCallback();
    final initialTime = isCurrent
        ? TimeOfDay(hour: now.hour, minute: now.minute)
        : const TimeOfDay(hour: 8, minute: 0);
    _configWeekStart = weekStart;
    _configCompact = compact;
    _configCurrentWeek = isCurrent;
    _viewConfiguration = _buildViewConfiguration(
      compact: compact,
      initialTime: initialTime,
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
    _syncViewConfiguration(compact: compact);
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
                bodyComponents: MultiDayBodyComponents(
                  hourLines: compact
                      ? null
                      : (context, heightPerMinute, timeOfDayRange) {
                          return WeekTodayColumnHourLines(
                            todayIndex: weekTodayColumnIndex(widget.week),
                            heightPerMinute: heightPerMinute,
                            timeOfDayRange: timeOfDayRange,
                          );
                        },
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
                eventLayoutStrategy:
                    const SecretaryDenseOverlapLayoutStrategy(),
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
    final compact =
        MediaQuery.sizeOf(context).width < AppSpacing.wideBreakpoint;
    var depth = 0;
    if (!event.isAllDay) {
      final date = InternalDateTime.fromDateTime(tileRange.start);
      final depths = weekOverlapDepthsOnDate(
        events: _events.events,
        date: date,
        location: KalenderScope.locationOf(context),
      );
      depth = depths[event.id] ?? 0;
    }
    return WeekKalenderEventTile(
      key: Key('week_event_${dayIso}_${event.id}'),
      objectId: event.id,
      title: secretary?.title ?? '',
      provider: secretary?.provider,
      allDay: event.isAllDay,
      bookmarkColor: widget.bookmarks.colorFor(event.id),
      depth: depth,
      compact: compact,
      itemType: secretary?.itemType ?? WeekTemporalItemType.calendarCommitment,
    );
  }
}

class _WeekDayHeader extends StatelessWidget {
  const _WeekDayHeader({required this.date, required this.todayDate});

  final DateTime date;
  final String todayDate;

  @override
  Widget build(BuildContext context) {
    final iso = formatCalendarDate(date);
    final isToday = iso == todayDate;
    final scheme = Theme.of(context).colorScheme;
    if (!isToday) {
      return Padding(
        key: Key('week_day_$iso'),
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
        child: Text(
          key: Key('week_day_header_$iso'),
          '${formatRussianWeekdayShort(date)} ${formatRussianDayMonth(date)}',
          textAlign: TextAlign.center,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: Theme.of(
            context,
          ).textTheme.labelMedium?.copyWith(fontWeight: FontWeight.w500),
        ),
      );
    }
    final fill = weekTodayBadgeFill(scheme);
    final onFill = weekTodayBadgeForeground(scheme);
    return Padding(
      key: Key('week_day_$iso'),
      padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 2),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            formatRussianWeekdayShort(date),
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(
              context,
            ).textTheme.labelSmall?.copyWith(fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 2),
          DecoratedBox(
            key: const Key('week_today_date_badge'),
            decoration: BoxDecoration(color: fill, shape: BoxShape.circle),
            child: SizedBox(
              width: kWeekTodayBadgeSize,
              height: kWeekTodayBadgeSize,
              child: Center(
                child: Text(
                  key: Key('week_day_today_$iso'),
                  '${date.day}',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: onFill,
                    fontWeight: FontWeight.w600,
                    height: 1,
                  ),
                ),
              ),
            ),
          ),
        ],
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
    this.depth = 0,
    this.compact = false,
    this.itemType = WeekTemporalItemType.calendarCommitment,
  });

  final String objectId;
  final String title;
  final String? provider;
  final bool allDay;
  final String? bookmarkColor;
  final int depth;
  final bool compact;
  final WeekTemporalItemType itemType;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final tone = weekOverlapTone(scheme, allDay ? 1 : depth);
    final denseTitle = !compact && !allDay;
    final typeColor = tone.foreground;
    final tokenColor = bookmarkColor == null
        ? null
        : bookmarkTokenColor(bookmarkColor!, scheme);
    return Material(
      color: tone.fill.withValues(alpha: 0.92),
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
            padding: EdgeInsets.fromLTRB(4, allDay ? 2 : 1, 4, allDay ? 2 : 1),
            child: Row(
              children: [
                _WeekEventIdentityRail(
                  objectId: objectId,
                  provider: provider,
                  itemType: itemType,
                  compact: !denseTitle,
                  typeColor: typeColor,
                ),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    title,
                    maxLines: allDay ? 1 : 3,
                    overflow: TextOverflow.ellipsis,
                    style: weekEventTitleStyle(
                      Theme.of(context).textTheme,
                      color: tone.foreground,
                      compact: !denseTitle,
                    ),
                  ),
                ),
                if (allDay)
                  Padding(
                    padding: const EdgeInsets.only(left: 4),
                    child: Text(
                      'Весь день',
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: tone.foreground.withValues(alpha: 0.8),
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
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    ObjectBookmarkGlyph(
                      fillColor: scheme.surface,
                      size: Size(
                        kBookmarkTabSize.width + 2,
                        kBookmarkTabSize.height + 2,
                      ),
                    ),
                    ObjectBookmarkGlyph(
                      key: Key('week_bookmark_$objectId'),
                      fillColor: tokenColor,
                      size: kBookmarkTabSize,
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _WeekEventIdentityRail extends StatelessWidget {
  const _WeekEventIdentityRail({
    required this.objectId,
    required this.provider,
    required this.itemType,
    required this.compact,
    required this.typeColor,
  });

  final String objectId;
  final String? provider;
  final WeekTemporalItemType itemType;
  final bool compact;
  final Color typeColor;

  @override
  Widget build(BuildContext context) {
    final providerSize = compact
        ? kWeekPhoneProviderGlyphSize
        : kWeekWideProviderGlyphSize;
    final typeSize = compact ? kWeekPhoneTypeGlyphSize : kWeekWideTypeGlyphSize;
    final glyph = compactProviderGlyphWidget(provider, size: providerSize);
    final needed =
        (glyph != null ? providerSize + kWeekIdentityRailGap : 0) + typeSize;
    final column = Column(
      key: Key('week_identity_rail_$objectId'),
      mainAxisSize: MainAxisSize.min,
      children: [
        if (glyph != null) ...[
          SizedBox(
            width: providerSize,
            height: providerSize,
            child: FittedBox(fit: BoxFit.contain, child: glyph),
          ),
          const SizedBox(height: kWeekIdentityRailGap),
        ],
        WeekTemporalItemTypeGlyph(
          objectId: objectId,
          itemType: itemType,
          size: typeSize,
          color: typeColor,
        ),
      ],
    );
    return IgnorePointer(
      child: LayoutBuilder(
        builder: (context, constraints) {
          final maxH = constraints.maxHeight;
          final fits = !maxH.isFinite || maxH >= needed;
          if (fits) {
            return column;
          }
          final railWidth = providerSize > typeSize ? providerSize : typeSize;
          return SizedBox(
            width: railWidth,
            height: maxH,
            child: ClipRect(
              child: OverflowBox(
                alignment: Alignment.topCenter,
                maxHeight: needed,
                child: column,
              ),
            ),
          );
        },
      ),
    );
  }
}
