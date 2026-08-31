import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../assistant/assistant_controller.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../navigation/secretary_navigation.dart';
import '../ui/date_format.dart';
import '../ui/object_presentation.dart';
import 'notification_labels.dart';

enum InboxLoadState { loading, ready, error }

class InboxScreen extends StatefulWidget {
  const InboxScreen({
    super.key,
    required this.apiClient,
    required this.authController,
    required this.captureController,
    this.assistantController,
    this.onAskSecretary,
    this.onAskSecretaryAboutNotification,
    this.onShowInGraph,
  });

  final SecretaryApiClient apiClient;
  final AuthController authController;
  final CaptureController captureController;
  final AssistantController? assistantController;
  final AskSecretaryHandler? onAskSecretary;
  final void Function(NotificationOut notification)? onAskSecretaryAboutNotification;
  final ShowInGraphHandler? onShowInGraph;

  @override
  State<InboxScreen> createState() => _InboxScreenState();
}

class _InboxScreenState extends State<InboxScreen> {
  InboxLoadState _loadState = InboxLoadState.loading;
  InboxOut? _inbox;
  String? _errorMessage;
  String? _mutatingNotificationId;

  @override
  void initState() {
    super.initState();
    _loadInbox();
  }

  Future<void> _loadInbox() async {
    if (!mounted) {
      return;
    }
    setState(() {
      _loadState = InboxLoadState.loading;
      _errorMessage = null;
    });

    try {
      final snapshot = await widget.apiClient.getInbox();
      if (!mounted) {
        return;
      }
      setState(() {
        _inbox = snapshot;
        _loadState = InboxLoadState.ready;
      });
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loadState = InboxLoadState.error;
        _errorMessage = e.message;
      });
    }
  }

  Future<void> _accept(NotificationOut notification) async {
    if (!mounted) {
      return;
    }
    setState(() => _mutatingNotificationId = notification.id);
    try {
      await widget.apiClient.acceptNotification(notification.id);
      if (!mounted) {
        return;
      }
      setState(() {
        final inbox = _inbox!;
        _inbox = InboxOut(
          unresolvedNotifications: inbox.unresolvedNotifications
              .where((row) => row.id != notification.id)
              .toList(),
          recentSourceObjects: inbox.recentSourceObjects,
          sourceSyncStatus: inbox.sourceSyncStatus,
        );
        _mutatingNotificationId = null;
      });
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _mutatingNotificationId = null;
        _errorMessage = e.message;
      });
    }
  }

  Future<void> _ignore(NotificationOut notification) async {
    if (!mounted) {
      return;
    }
    setState(() => _mutatingNotificationId = notification.id);
    try {
      await widget.apiClient.ignoreNotification(notification.id);
      if (!mounted) {
        return;
      }
      setState(() {
        final inbox = _inbox!;
        _inbox = InboxOut(
          unresolvedNotifications: inbox.unresolvedNotifications
              .where((row) => row.id != notification.id)
              .toList(),
          recentSourceObjects: inbox.recentSourceObjects,
          sourceSyncStatus: inbox.sourceSyncStatus,
        );
        _mutatingNotificationId = null;
      });
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _mutatingNotificationId = null;
        _errorMessage = e.message;
      });
    }
  }

  void _openSourceObject(InboxSourceObjectOut sourceObject) {
    openObjectDetail(
      context,
      objectId: sourceObject.id,
      apiClient: widget.apiClient,
      authController: widget.authController,
      captureController: widget.captureController,
      assistantController: widget.assistantController,
      onAskSecretary: widget.onAskSecretary,
      onShowInGraph: widget.onShowInGraph,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Align(
          alignment: Alignment.centerRight,
          child: IconButton(
            tooltip: 'Обновить',
            onPressed: _loadInbox,
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
      case InboxLoadState.error:
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_errorMessage ?? 'Не удалось загрузить входящие'),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _loadInbox,
                child: const Text('Повторить'),
              ),
            ],
          ),
        );
      case InboxLoadState.ready:
        final inbox = _inbox!;
        final hasNotifications = inbox.unresolvedNotifications.isNotEmpty;
        final hasSources = inbox.recentSourceObjects.isNotEmpty;
        if (!hasNotifications && !hasSources) {
          return const Center(child: Text('Входящие пусты'));
        }
        return ListView(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          children: [
            if (inbox.sourceSyncStatus.any((row) => row.status == 'error'))
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(
                    'Некоторые источники не синхронизированы. '
                    'Проверьте подключения или повторите позже.',
                  ),
                ),
              ),
            const _SectionHeader(title: 'Требует внимания'),
            if (!hasNotifications)
              const Padding(
                padding: EdgeInsets.only(bottom: 8),
                child: Text('Нет уведомлений'),
              )
            else
              ...inbox.unresolvedNotifications.map(
                (notification) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _NotificationCard(
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
                      assistantController: widget.assistantController,
                      onAskSecretary: widget.onAskSecretary,
                      onAskSecretaryAboutNotification:
                          widget.onAskSecretaryAboutNotification,
                      onShowInGraph: widget.onShowInGraph,
                    ),
                  ),
                ),
              ),
            const SizedBox(height: 16),
            const _SectionHeader(title: 'Последние из источников'),
            if (!hasSources)
              const Padding(
                padding: EdgeInsets.only(bottom: 8),
                child: Text('Нет недавних объектов из источников'),
              )
            else
              ...inbox.recentSourceObjects.map(
                (sourceObject) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _SourceObjectCard(
                    sourceObject: sourceObject,
                    onTap: () => _openSourceObject(sourceObject),
                    onAskSecretary: widget.onAskSecretary == null
                        ? null
                        : () {
                            widget.onAskSecretary!(
                              SecretaryObject(
                                id: sourceObject.id,
                                kind: sourceObject.kind,
                                title: sourceObject.title,
                                body: sourceObject.excerpt,
                                provider: sourceObject.provider,
                                externalId: null,
                                canonicalUri: null,
                                status: sourceObject.status,
                                startAt: null,
                                dueAt: null,
                                occurredAt: sourceObject.primaryAt,
                                metadata: const {},
                                origin: 'source',
                                state: sourceObject.state,
                                confidence: null,
                                createdAt: sourceObject.primaryAt ?? '',
                                updatedAt: sourceObject.primaryAt ?? '',
                              ),
                            );
                          },
                    onShowInGraph: widget.onShowInGraph == null
                        ? null
                        : () => widget.onShowInGraph!(sourceObject.id),
                  ),
                ),
              ),
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
            Text('Приоритет: ${notificationPriorityLabel(notification.priority)}'),
            if (notification.proposalType != null)
              Text(
                'Тип: ${notificationProposalTypeLabel(notification.proposalType!)}',
              ),
            Text('Источник: ${notificationEvidenceLabel(notification)}'),
            if (notification.proposalDescription != null)
              Text(notification.proposalDescription!),
            if (notification.proposedAction != null)
              Text(
                'Действие: ${notificationProposedActionLabel(notification.proposedAction!)}',
              ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                FilledButton(
                  onPressed: isMutating ? null : onAccept,
                  child: const Text('Принять'),
                ),
                OutlinedButton(
                  onPressed: isMutating ? null : onIgnore,
                  child: const Text('Пропустить'),
                ),
                TextButton(
                  onPressed: isMutating ? null : onOpenContext,
                  child: const Text('Открыть контекст'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _SourceObjectCard extends StatelessWidget {
  const _SourceObjectCard({
    required this.sourceObject,
    required this.onTap,
    this.onAskSecretary,
    this.onShowInGraph,
  });

  final InboxSourceObjectOut sourceObject;
  final VoidCallback onTap;
  final VoidCallback? onAskSecretary;
  final VoidCallback? onShowInGraph;

  @override
  Widget build(BuildContext context) {
    final when = formatUserDateTime(sourceObject.primaryAt);
    final provider = providerLabel(sourceObject.provider);
    return Card(
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  providerCompactIcon(sourceObject.provider),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      sourceObject.title,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                '${objectKindLabel(sourceObject.kind)} • $provider'
                '${when.isNotEmpty ? ' • $when' : ''}',
              ),
              if (sourceObject.excerpt != null)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(sourceObject.excerpt!),
                ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  if (onAskSecretary != null)
                    TextButton(
                      onPressed: onAskSecretary,
                      child: const Text('Спросить секретаря'),
                    ),
                  if (onShowInGraph != null)
                    TextButton(
                      onPressed: onShowInGraph,
                      child: const Text('Показать в графе'),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
