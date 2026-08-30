import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../assistant/assistant_controller.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../inbox/notification_labels.dart';
import '../navigation/secretary_navigation.dart';

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
  });

  final SecretaryApiClient apiClient;
  final AuthController authController;
  final CaptureController captureController;
  final AssistantController? assistantController;
  final AskSecretaryHandler? onAskSecretary;
  final ShowInGraphHandler? onShowInGraph;

  @override
  State<TodayScreen> createState() => _TodayScreenState();
}

class _TodayScreenState extends State<TodayScreen> {
  TodayLoadState _loadState = TodayLoadState.loading;
  TodayOut? _today;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadToday();
  }

  Future<void> _loadToday() async {
    if (!mounted) {
      return;
    }
    setState(() {
      _loadState = TodayLoadState.loading;
      _errorMessage = null;
    });

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
      setState(() {
        _loadState = TodayLoadState.error;
        _errorMessage = e.message;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Align(
          alignment: Alignment.centerRight,
          child: IconButton(
            tooltip: 'Refresh',
            onPressed: _loadToday,
            icon: const Icon(Icons.refresh),
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
              Text(_errorMessage ?? 'Failed to load today'),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _loadToday,
                child: const Text('Retry'),
              ),
            ],
          ),
        );
      case TodayLoadState.ready:
        final today = _today!;
        return ListView(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          children: [
            Text('${today.date} (${today.timezone})'),
            const SizedBox(height: 16),
            _SectionHeader(title: 'Tasks'),
            if (today.tasks.isEmpty)
              const _EmptySection(message: 'No tasks for today')
            else
              ...today.tasks.map((task) => _TaskRow(
                    task: task,
                    today: today,
                    onTap: () => openObjectDetail(
                      context,
                      objectId: task.id,
                      apiClient: widget.apiClient,
                      authController: widget.authController,
                      captureController: widget.captureController,
                      assistantController: widget.assistantController,
                      onAskSecretary: widget.onAskSecretary,
                      onShowInGraph: widget.onShowInGraph,
                    ),
                  )),
            const SizedBox(height: 16),
            _SectionHeader(title: 'Calendar'),
            if (today.calendarEvents.isEmpty)
              const _EmptySection(message: 'No calendar events today')
            else
              ...today.calendarEvents.map((event) => _EventRow(
                    event: event,
                    onTap: () => openObjectDetail(
                      context,
                      objectId: event.id,
                      apiClient: widget.apiClient,
                      authController: widget.authController,
                      captureController: widget.captureController,
                      assistantController: widget.assistantController,
                      onAskSecretary: widget.onAskSecretary,
                      onShowInGraph: widget.onShowInGraph,
                    ),
                  )),
            const SizedBox(height: 16),
            _SectionHeader(title: 'Important notifications'),
            if (today.notifications.isEmpty)
              const _EmptySection(message: 'No important notifications')
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
    return ListTile(
      title: Text(task.title),
      subtitle: Text(
        overdue ? 'Overdue • ${_formatWhen(task.dueAt)}' : _formatWhen(task.dueAt),
      ),
      onTap: onTap,
    );
  }

  String _formatWhen(String? value) {
    if (value == null) {
      return 'No due time';
    }
    final parsed = DateTime.tryParse(value);
    if (parsed == null) {
      return value;
    }
    final local = parsed.toLocal();
    return '${local.year}-${local.month.toString().padLeft(2, '0')}-${local.day.toString().padLeft(2, '0')} '
        '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
  }
}

class _EventRow extends StatelessWidget {
  const _EventRow({required this.event, required this.onTap});

  final SecretaryObject event;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(event.title),
      subtitle: Text(
        '${_formatWhen(event.startAt)}'
        '${event.provider != null ? ' • ${event.provider}' : ''}',
      ),
      onTap: onTap,
    );
  }

  String _formatWhen(String? value) {
    if (value == null) {
      return 'No start time';
    }
    final parsed = DateTime.tryParse(value);
    if (parsed == null) {
      return value;
    }
    final local = parsed.toLocal();
    return '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
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
      subtitle: Text('${notification.priority} • ${notificationEvidenceLabel(notification)}'),
      onTap: onTap,
    );
  }
}
