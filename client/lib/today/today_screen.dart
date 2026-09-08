import 'dart:async';

import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../assistant/assistant_controller.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../inbox/notification_labels.dart';
import '../navigation/secretary_navigation.dart';
import '../sources/source_refresh_service.dart';
import '../ui/date_format.dart';
import '../ui/object_presentation.dart';
import '../ui/passive_snapshot_refresh.dart';
import '../ui/today_event_emphasis.dart';

enum TodayLoadState { loading, ready, error }

class TodayScreen extends StatefulWidget {
  const TodayScreen({
    super.key,
    required this.apiClient,
    required this.authController,
    required this.captureController,
    this.assistantController,
    this.onAskSecretary,
    this.onShowInGraph,
    this.passiveRefreshInterval = kPassiveSnapshotRefreshInterval,
    this.now,
    this.clockTick = const Duration(minutes: 1),
  });

  final SecretaryApiClient apiClient;
  final AuthController authController;
  final CaptureController captureController;
  final AssistantController? assistantController;
  final AskSecretaryHandler? onAskSecretary;
  final ShowInGraphHandler? onShowInGraph;
  final Duration passiveRefreshInterval;
  final DateTime Function()? now;
  final Duration clockTick;

  @override
  State<TodayScreen> createState() => _TodayScreenState();
}

class _TodayScreenState extends State<TodayScreen> {
  TodayLoadState _loadState = TodayLoadState.loading;
  TodayOut? _today;
  String? _errorMessage;
  String? _refreshStatusMessage;
  bool _isSourceRefreshing = false;
  late DateTime _now;
  Timer? _clock;

  late final SourceRefreshService _sourceRefreshService =
      SourceRefreshService(apiClient: widget.apiClient);
  late final PassiveSnapshotRefresh _passiveRefresh;

  @override
  void initState() {
    super.initState();
    _now = (widget.now ?? DateTime.now)().toLocal();
    _clock = Timer.periodic(widget.clockTick, (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _now = (widget.now ?? DateTime.now)().toLocal();
      });
    });
    _passiveRefresh = PassiveSnapshotRefresh(
      interval: widget.passiveRefreshInterval,
      isPaused: () => _isSourceRefreshing,
      onRefresh: () => _loadToday(showFullLoader: false, passive: true),
    );
    _passiveRefresh.attach();
    _loadToday();
  }

  @override
  void dispose() {
    _clock?.cancel();
    _passiveRefresh.dispose();
    super.dispose();
  }

  Future<void> _loadToday(
      {bool showFullLoader = true, bool passive = false}) async {
    if (!mounted) {
      return;
    }
    if (passive && _isSourceRefreshing) {
      return;
    }
    if (showFullLoader && !passive) {
      setState(() {
        _loadState = TodayLoadState.loading;
        _errorMessage = null;
      });
    }

    try {
      final snapshot = await widget.apiClient.getToday();
      if (!mounted) {
        return;
      }
      setState(() {
        _today = snapshot;
        _loadState = TodayLoadState.ready;
      });
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      if (passive && _today != null) {
        return;
      }
      setState(() {
        _loadState = TodayLoadState.error;
        _errorMessage = e.message;
      });
    }
  }

  Future<void> _refreshWithSources() async {
    if (!mounted) {
      return;
    }
    setState(() {
      _isSourceRefreshing = true;
      _refreshStatusMessage = null;
      if (_today == null) {
        _loadState = TodayLoadState.loading;
      }
    });
    try {
      final result = await _sourceRefreshService.refreshSources();
      if (!mounted) {
        return;
      }
      await _loadToday(showFullLoader: _today == null);
      if (!mounted) {
        return;
      }
      if (result.timedOut) {
        setState(() {
          _refreshStatusMessage = 'Синхронизация источников продолжается';
        });
      }
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _refreshStatusMessage = e.message;
        if (_today == null) {
          _loadState = TodayLoadState.error;
          _errorMessage = e.message;
        }
      });
    } finally {
      if (mounted) {
        setState(() => _isSourceRefreshing = false);
      }
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
    );
    if (!mounted || result == null) {
      return;
    }
    final today = _today;
    if (today == null) {
      return;
    }
    setState(() {
      _today = TodayOut(
        date: today.date,
        timezone: today.timezone,
        dayStart: today.dayStart,
        tasks: today.tasks
            .where((task) => task.id != result.deletedObjectId)
            .toList(),
        calendarEvents: today.calendarEvents
            .where((event) => event.id != result.deletedObjectId)
            .toList(),
        notifications: today.notifications,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Align(
          alignment: Alignment.centerRight,
          child: IconButton(
            tooltip: 'Обновить',
            onPressed: _isSourceRefreshing ? null : _refreshWithSources,
            icon: _isSourceRefreshing
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh),
          ),
        ),
        Expanded(child: _buildBody()),
      ],
    );
  }

  Widget _buildBody() {
    switch (_loadState) {
      case TodayLoadState.loading:
        return const Center(child: CircularProgressIndicator());
      case TodayLoadState.error:
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_errorMessage ?? 'Не удалось загрузить «Сегодня»'),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _loadToday,
                child: const Text('Повторить'),
              ),
            ],
          ),
        );
      case TodayLoadState.ready:
        final today = _today!;
        return ListView(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          children: [
            if (_refreshStatusMessage != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(_refreshStatusMessage!),
              ),
            Text('${today.date} (${today.timezone})'),
            const SizedBox(height: 16),
            _SectionHeader(title: 'Задачи'),
            if (today.tasks.isEmpty)
              const _EmptySection(message: 'Нет задач на сегодня')
            else
              ...today.tasks.map((task) => _TaskRow(
                    task: task,
                    today: today,
                    onTap: () => _openObjectDetail(task.id),
                  )),
            const SizedBox(height: 16),
            _SectionHeader(title: 'Календарь'),
            if (today.calendarEvents.isEmpty)
              const _EmptySection(message: 'Нет событий в календаре')
            else
              ...today.calendarEvents.map((event) => _EventRow(
                    event: event,
                    emphasis: todayEventEmphasis(event, now: _now),
                    onTap: () => _openObjectDetail(event.id),
                  )),
            const SizedBox(height: 16),
            _SectionHeader(title: 'Важные уведомления'),
            if (today.notifications.isEmpty)
              const _EmptySection(message: 'Нет важных уведомлений')
            else
              ...today.notifications.map((notification) => _NotificationRow(
                    notification: notification,
                    onTap: () => openNotificationContext(
                      context,
                      notification: notification,
                      apiClient: widget.apiClient,
                      authController: widget.authController,
                      captureController: widget.captureController,
                      assistantController: widget.assistantController,
                      onAskSecretary: widget.onAskSecretary,
                      onShowInGraph: widget.onShowInGraph,
                    ),
                  )),
          ],
        );
    }
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(title, style: Theme.of(context).textTheme.titleMedium),
    );
  }
}

class _EmptySection extends StatelessWidget {
  const _EmptySection({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(message),
    );
  }
}

class _TaskRow extends StatelessWidget {
  const _TaskRow({
    required this.task,
    required this.today,
    required this.onTap,
  });

  final SecretaryObject task;
  final TodayOut today;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final overdue = today.isTaskOverdue(task);
    final dueAt = formatUserDateTime(task.dueAt);
    final when = dueAt.isEmpty ? 'Нет срока' : dueAt;
    final trailing = overdue ? 'Просрочено • $when' : when;
    return ListTile(
      title: ObjectCompactHeaderRow(
        title: task.title,
        kind: task.kind,
        provider: task.provider,
        trailingText: trailing,
        trailingBadges: task.state == 'proposed'
            ? [
                Padding(
                  padding: const EdgeInsets.only(left: 6),
                  child: Text(
                    'Предложено',
                    style: Theme.of(context).textTheme.labelMedium,
                  ),
                ),
              ]
            : const [],
      ),
      onTap: onTap,
    );
  }
}

class _EventRow extends StatelessWidget {
  const _EventRow({
    required this.event,
    required this.emphasis,
    required this.onTap,
  });

  final SecretaryObject event;
  final TodayEventEmphasis emphasis;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final time = formatUserTime(event.startAt);
    final scheme = Theme.of(context).colorScheme;
    Color? background;
    Color? stripe;
    switch (emphasis) {
      case TodayEventEmphasis.current:
        background = scheme.errorContainer.withValues(alpha: 0.35);
        stripe = scheme.error;
      case TodayEventEmphasis.soon:
        background = scheme.tertiaryContainer.withValues(alpha: 0.45);
        stripe = scheme.tertiary;
      case TodayEventEmphasis.none:
        break;
    }
    return DecoratedBox(
      key: Key('today_event_${emphasis.name}_${event.id}'),
      decoration: BoxDecoration(
        color: background,
        border: stripe == null
            ? null
            : Border(left: BorderSide(color: stripe, width: 3)),
      ),
      child: ListTile(
        title: ObjectCompactHeaderRow(
          title: event.title,
          kind: event.kind,
          provider: event.provider,
          trailingText: time.isEmpty ? 'Нет времени' : time,
        ),
        onTap: onTap,
      ),
    );
  }
}

class _NotificationRow extends StatelessWidget {
  const _NotificationRow({required this.notification, required this.onTap});

  final NotificationOut notification;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(notification.title),
      subtitle: Text(
        '${notificationPriorityLabel(notification.priority)} • ${notificationEvidenceLabel(notification)}',
      ),
      onTap: onTap,
    );
  }
}
