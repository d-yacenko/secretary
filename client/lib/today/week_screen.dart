import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../assistant/assistant_controller.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../navigation/secretary_navigation.dart';
import '../ui/assigned_labels_loader.dart';
import '../ui/date_format.dart';
import '../ui/object_bookmark.dart';
import '../ui/object_bookmark_controller.dart';
import '../ui/object_label_strip.dart';
import '../ui/object_presentation.dart';

enum WeekLoadState { loading, ready, error }

class WeekScreen extends StatefulWidget {
  const WeekScreen({
    super.key,
    required this.apiClient,
    required this.authController,
    required this.captureController,
    this.assistantController,
    this.onAskSecretary,
    this.onShowInGraph,
    this.bookmarkController,
  });

  final SecretaryApiClient apiClient;
  final AuthController authController;
  final CaptureController captureController;
  final AssistantController? assistantController;
  final AskSecretaryHandler? onAskSecretary;
  final ShowInGraphHandler? onShowInGraph;
  final ObjectBookmarkController? bookmarkController;

  @override
  State<WeekScreen> createState() => _WeekScreenState();
}

class _WeekScreenState extends State<WeekScreen> {
  WeekLoadState _loadState = WeekLoadState.loading;
  WeekOut? _week;
  String? _requestedWeekStart;
  Map<String, List<LabelItem>> _labelsByObject = {};
  String? _errorMessage;
  late final ObjectBookmarkController _bookmarks;
  var _ownsBookmarks = false;

  @override
  void initState() {
    super.initState();
    final provided = widget.bookmarkController;
    if (provided != null) {
      _bookmarks = provided;
    } else {
      _ownsBookmarks = true;
      _bookmarks = ObjectBookmarkController(
        apiClient: widget.apiClient,
        authController: widget.authController,
      );
    }
    _bookmarks.addListener(_onBookmarksChanged);
    _loadWeek();
  }

  @override
  void dispose() {
    _bookmarks.removeListener(_onBookmarksChanged);
    if (_ownsBookmarks) {
      _bookmarks.dispose();
    }
    super.dispose();
  }

  void _onBookmarksChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  Future<void> _loadWeek({String? weekStart, bool showFullLoader = true}) async {
    if (!mounted) {
      return;
    }
    if (showFullLoader) {
      setState(() {
        _loadState = WeekLoadState.loading;
        _errorMessage = null;
      });
    }
    try {
      final snapshot = await widget.apiClient.getWeek(weekStart: weekStart);
      if (!mounted) {
        return;
      }
      setState(() {
        _week = snapshot;
        _requestedWeekStart = snapshot.weekStart;
        _loadState = WeekLoadState.ready;
      });
      final ids = [
        for (final day in snapshot.days)
          for (final event in day.events) event.object.id,
      ];
      final labels = await loadAssignedLabelsByObjects(
        apiClient: widget.apiClient,
        onAuthFailure: widget.authController.handleAuthenticationFailure,
        objectIds: ids,
      );
      if (!mounted) {
        return;
      }
      setState(() => _labelsByObject = labels);
      await _bookmarks.reconcileVisible(ids);
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loadState = WeekLoadState.error;
        _errorMessage = e.message;
      });
    }
  }

  Future<void> _openObjectDetail(String objectId) async {
    final result = await openObjectDetail(
      context,
      objectId: objectId,
      apiClient: widget.apiClient,
      authController: widget.authController,
      captureController: widget.captureController,
      assistantController: widget.assistantController,
      onAskSecretary: widget.onAskSecretary,
      onShowInGraph: widget.onShowInGraph,
      bookmarkController: _bookmarks,
    );
    if (!mounted || result == null || _week == null) {
      return;
    }
    setState(() {
      _week = WeekOut(
        weekStart: _week!.weekStart,
        weekEnd: _week!.weekEnd,
        timezone: _week!.timezone,
        windowStart: _week!.windowStart,
        windowEnd: _week!.windowEnd,
        todayDate: _week!.todayDate,
        isCurrentWeek: _week!.isCurrentWeek,
        days: [
          for (final day in _week!.days)
            WeekDay(
              date: day.date,
              isToday: day.isToday,
              events: day.events
                  .where((event) => event.object.id != result.deletedObjectId)
                  .toList(),
            ),
        ],
      );
    });
    _bookmarks.forget(result.deletedObjectId);
  }

  void _goRelative(int days) {
    final current = _week?.weekStart ?? _requestedWeekStart;
    if (current == null) {
      return;
    }
    final next = parseCalendarDate(current).add(Duration(days: days));
    _loadWeek(weekStart: formatCalendarDate(next));
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _WeekNavigationBar(
          week: _week,
          enabled: _loadState != WeekLoadState.loading,
          onPrevious: () => _goRelative(-7),
          onNext: () => _goRelative(7),
          onCurrent: () => _loadWeek(),
        ),
        Expanded(child: _buildBody()),
      ],
    );
  }

  Widget _buildBody() {
    switch (_loadState) {
      case WeekLoadState.loading:
        return const Center(child: CircularProgressIndicator());
      case WeekLoadState.error:
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_errorMessage ?? 'Не удалось загрузить неделю'),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: () => _loadWeek(weekStart: _requestedWeekStart),
                child: const Text('Повторить'),
              ),
            ],
          ),
        );
      case WeekLoadState.ready:
        final week = _week!;
        final empty = week.days.every((day) => day.events.isEmpty);
        return ListView(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          children: [
            if (empty)
              const Padding(
                padding: EdgeInsets.only(bottom: 12),
                child: Text('На этой неделе событий нет'),
              ),
            for (final day in week.days)
              _WeekDaySection(
                day: day,
                labelsByObject: _labelsByObject,
                bookmarks: _bookmarks,
                onOpen: _openObjectDetail,
              ),
          ],
        );
    }
  }
}

class _WeekNavigationBar extends StatelessWidget {
  const _WeekNavigationBar({
    required this.week,
    required this.enabled,
    required this.onPrevious,
    required this.onNext,
    required this.onCurrent,
  });

  final WeekOut? week;
  final bool enabled;
  final VoidCallback onPrevious;
  final VoidCallback onNext;
  final VoidCallback onCurrent;

  @override
  Widget build(BuildContext context) {
    final range = week == null ? 'Неделя' : formatWeekRange(week!.weekStart);
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 4, 4, 0),
      child: Row(
        children: [
          IconButton(
            key: const Key('week_nav_prev'),
            tooltip: 'Предыдущая неделя',
            onPressed: enabled ? onPrevious : null,
            icon: const Icon(Icons.chevron_left),
          ),
          Expanded(
            child: Text(
              key: const Key('week_range'),
              range,
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.titleSmall,
            ),
          ),
          if (week != null && !week!.isCurrentWeek)
            TextButton(
              key: const Key('week_nav_current'),
              onPressed: enabled ? onCurrent : null,
              child: const Text('Эта неделя'),
            ),
          IconButton(
            key: const Key('week_nav_next'),
            tooltip: 'Следующая неделя',
            onPressed: enabled ? onNext : null,
            icon: const Icon(Icons.chevron_right),
          ),
        ],
      ),
    );
  }
}

class _WeekDaySection extends StatelessWidget {
  const _WeekDaySection({
    required this.day,
    required this.labelsByObject,
    required this.bookmarks,
    required this.onOpen,
  });

  final WeekDay day;
  final Map<String, List<LabelItem>> labelsByObject;
  final ObjectBookmarkController bookmarks;
  final ValueChanged<String> onOpen;

  @override
  Widget build(BuildContext context) {
    final date = parseCalendarDate(day.date);
    final header = '${formatRussianWeekdayShort(date)} ${formatRussianDayMonth(date)}';
    final scheme = Theme.of(context).colorScheme;
    final headerStyle = Theme.of(context).textTheme.titleSmall?.copyWith(
          color: day.isToday ? scheme.primary : null,
          fontWeight: day.isToday ? FontWeight.w600 : FontWeight.w500,
        );
    return Padding(
      key: Key('week_day_${day.date}'),
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          DecoratedBox(
            decoration: BoxDecoration(
              color: day.isToday
                  ? scheme.primaryContainer.withValues(alpha: 0.45)
                  : null,
              borderRadius: BorderRadius.circular(6),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              child: Text(
                key: Key(day.isToday
                    ? 'week_day_today_${day.date}'
                    : 'week_day_header_${day.date}'),
                header,
                style: headerStyle,
              ),
            ),
          ),
          if (day.events.isEmpty)
            const SizedBox(height: 4)
          else
            for (final event in day.events)
              _WeekEventRow(
                event: event,
                labels: labelsByObject[event.object.id] ?? const [],
                bookmarkColor: bookmarks.colorFor(event.object.id),
                onBookmarkSelect: (color) =>
                    bookmarks.setColor(event.object.id, color),
                onBookmarkClear: () => bookmarks.clear(event.object.id),
                onTap: () => onOpen(event.object.id),
              ),
        ],
      ),
    );
  }
}

class _WeekEventRow extends StatelessWidget {
  const _WeekEventRow({
    required this.event,
    required this.labels,
    required this.bookmarkColor,
    required this.onBookmarkSelect,
    required this.onBookmarkClear,
    required this.onTap,
  });

  final WeekEvent event;
  final List<LabelItem> labels;
  final String? bookmarkColor;
  final ValueChanged<String> onBookmarkSelect;
  final VoidCallback onBookmarkClear;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final time = event.allDay
        ? 'Весь день'
        : formatUserTime(event.object.startAt);
    return ObjectBookmarkRibbon(
      color: bookmarkColor,
      onSelect: onBookmarkSelect,
      onClear: onBookmarkClear,
      child: ListTile(
        key: Key('week_event_${event.object.id}'),
        dense: true,
        contentPadding: EdgeInsets.zero,
        title: ObjectCompactHeaderRow(
          title: event.object.title,
          kind: event.object.kind,
          provider: event.object.provider,
          trailingText: time.isEmpty ? 'Нет времени' : time,
          trailingReserve: bookmarkColor != null ? kBookmarkRibbonReserve : 0,
        ),
        subtitle: _weekBookmarkSubtitle(
          labels: labels,
          bookmarkColor: bookmarkColor,
          onSelect: onBookmarkSelect,
          onClear: onBookmarkClear,
        ),
        onTap: onTap,
      ),
    );
  }
}

Widget? _weekBookmarkSubtitle({
  required List<LabelItem> labels,
  required String? bookmarkColor,
  required ValueChanged<String> onSelect,
  required VoidCallback onClear,
}) {
  final actions = <Widget>[
    if (bookmarkColor == null)
      ObjectBookmarkControl(
        color: bookmarkColor,
        onSelect: onSelect,
        onClear: onClear,
      ),
  ];
  if (actions.isEmpty && labels.isEmpty) {
    return null;
  }
  return ObjectMetaActionRow(
    actions: actions,
    labels: labels,
  );
}