import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../navigation/secretary_navigation.dart';
import 'notification_labels.dart';

enum InboxLoadState { loading, ready, empty, error }

class InboxScreen extends StatefulWidget {
  const InboxScreen({
    super.key,
    required this.apiClient,
    required this.authController,
    required this.captureController,
  });

  final SecretaryApiClient apiClient;
  final AuthController authController;
  final CaptureController captureController;

  @override
  State<InboxScreen> createState() => _InboxScreenState();
}

class _InboxScreenState extends State<InboxScreen> {
  InboxLoadState _loadState = InboxLoadState.loading;
  List<NotificationOut> _notifications = [];
  String? _errorMessage;
  String? _mutatingNotificationId;

  @override
  void initState() {
    super.initState();
    _loadNotifications();
  }

  Future<void> _loadNotifications() async {
    setState(() {
      _loadState = InboxLoadState.loading;
      _errorMessage = null;
    });

    try {
      final rows = await widget.apiClient.listUnresolvedNotifications();
      setState(() {
        _notifications = rows;
        _loadState = rows.isEmpty ? InboxLoadState.empty : InboxLoadState.ready;
      });
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      setState(() {
        _loadState = InboxLoadState.error;
        _errorMessage = e.message;
      });
    }
  }

  Future<void> _accept(NotificationOut notification) async {
    setState(() => _mutatingNotificationId = notification.id);
    try {
      await widget.apiClient.acceptNotification(notification.id);
      setState(() {
        _notifications = _notifications
            .where((row) => row.id != notification.id)
            .toList();
        _loadState =
            _notifications.isEmpty ? InboxLoadState.empty : InboxLoadState.ready;
        _mutatingNotificationId = null;
      });
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      setState(() {
        _mutatingNotificationId = null;
        _errorMessage = e.message;
      });
    }
  }

  Future<void> _ignore(NotificationOut notification) async {
    setState(() => _mutatingNotificationId = notification.id);
    try {
      await widget.apiClient.ignoreNotification(notification.id);
      setState(() {
        _notifications = _notifications
            .where((row) => row.id != notification.id)
            .toList();
        _loadState =
            _notifications.isEmpty ? InboxLoadState.empty : InboxLoadState.ready;
        _mutatingNotificationId = null;
      });
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      setState(() {
        _mutatingNotificationId = null;
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
            onPressed: _loadNotifications,
            icon: const Icon(Icons.refresh),
          ),
        ),
        Expanded(child: _buildBody()),
      ],
    );
  }

  Widget _buildBody() {
    switch (_loadState) {
      case InboxLoadState.loading:
        return const Center(child: CircularProgressIndicator());
      case InboxLoadState.empty:
        return const Center(child: Text('Inbox is empty'));
      case InboxLoadState.error:
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_errorMessage ?? 'Failed to load inbox'),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _loadNotifications,
                child: const Text('Retry'),
              ),
            ],
          ),
        );
      case InboxLoadState.ready:
        return ListView.separated(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          itemCount: _notifications.length,
          separatorBuilder: (_, __) => const SizedBox(height: 8),
          itemBuilder: (context, index) {
            final notification = _notifications[index];
            return _NotificationCard(
              notification: notification,
              isMutating: _mutatingNotificationId == notification.id,
              onAccept: () => _accept(notification),
              onIgnore: () => _ignore(notification),
              onOpenContext: () => openNotificationContext(
                context,
                notification: notification,
                apiClient: widget.apiClient,
                authController: widget.authController,
                captureController: widget.captureController,
              ),
            );
          },
        );
    }
  }
}

class _NotificationCard extends StatelessWidget {
  const _NotificationCard({
    required this.notification,
    required this.isMutating,
    required this.onAccept,
    required this.onIgnore,
    required this.onOpenContext,
  });

  final NotificationOut notification;
  final bool isMutating;
  final VoidCallback onAccept;
  final VoidCallback onIgnore;
  final VoidCallback onOpenContext;

  @override
  Widget build(BuildContext context) {
    final urgent = notificationIsUrgent(notification);
    final isNew = notification.status == 'new';
    final colorScheme = Theme.of(context).colorScheme;

    return Card(
      color: urgent
          ? colorScheme.errorContainer.withValues(alpha: isNew ? 0.35 : 0.2)
          : isNew
              ? colorScheme.surfaceContainerHighest
              : null,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              notification.title,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 4),
            Text('Priority: ${notification.priority}'),
            if (notification.proposalType != null)
              Text('Type: ${notification.proposalType}'),
            Text('Source: ${notificationEvidenceLabel(notification)}'),
            if (notification.proposalDescription != null)
              Text(notification.proposalDescription!),
            if (notification.proposedAction != null)
              Text('Action: ${notification.proposedAction}'),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                FilledButton(
                  onPressed: isMutating ? null : onAccept,
                  child: const Text('Accept'),
                ),
                OutlinedButton(
                  onPressed: isMutating ? null : onIgnore,
                  child: const Text('Ignore'),
                ),
                TextButton(
                  onPressed: isMutating ? null : onOpenContext,
                  child: const Text('Open context'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
