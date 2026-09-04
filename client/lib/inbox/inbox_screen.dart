import 'dart:io';

import 'package:desktop_drop/desktop_drop.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../assistant/assistant_controller.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../local/local_intake_actions.dart';
import '../navigation/secretary_navigation.dart';
import '../sources/source_refresh_service.dart';
import '../sources/source_sync_error_presentation.dart';
import '../ui/date_format.dart';
import '../ui/object_presentation.dart';
import '../ui/passive_snapshot_refresh.dart';
import '../voice/voice_transcription_controller.dart';
import 'inbox_intake_url.dart';
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
    this.passiveRefreshInterval = kPassiveSnapshotRefreshInterval,
    this.sourceRefreshTimeout,
    this.sourceRefreshPollInterval,
  });

  final SecretaryApiClient apiClient;
  final AuthController authController;
  final CaptureController captureController;
  final AssistantController? assistantController;
  final AskSecretaryHandler? onAskSecretary;
  final void Function(NotificationOut notification)?
      onAskSecretaryAboutNotification;
  final ShowInGraphHandler? onShowInGraph;
  final Duration passiveRefreshInterval;
  final Duration? sourceRefreshTimeout;
  final Duration? sourceRefreshPollInterval;

  @override
  State<InboxScreen> createState() => InboxScreenState();
}

class InboxScreenState extends State<InboxScreen> {
  InboxLoadState _loadState = InboxLoadState.loading;
  InboxOut? _inbox;
  String? _errorMessage;
  String? _mutatingNotificationId;
  String? _refreshStatusMessage;
  String? _intakeErrorMessage;
  bool _isSourceRefreshing = false;
  bool _isIntakePending = false;
  bool _isDragHovering = false;

  final TextEditingController _intakeController = TextEditingController();
  late final VoiceTranscriptionController _voice;

  late final SourceRefreshService _sourceRefreshService =
      SourceRefreshService(apiClient: widget.apiClient);
  late final PassiveSnapshotRefresh _passiveRefresh;
  late final LocalIntakeActions _localIntakeActions;

  @override
  void initState() {
    super.initState();
    _localIntakeActions = LocalIntakeActions(
      apiClient: widget.apiClient,
      authController: widget.authController,
      forInbox: true,
      onIntakeSuccess: _onLocalIntakeSuccess,
    );
    _voice = VoiceTranscriptionController(
      apiClient: widget.apiClient,
      authController: widget.authController,
    );
    _voice.bindTranscriptConsumer(_handleVoiceTranscript);
    _voice.addListener(_onVoiceChanged);
    _passiveRefresh = PassiveSnapshotRefresh(
      interval: widget.passiveRefreshInterval,
      isPaused: () => _isSourceRefreshing,
      onRefresh: () => _loadInbox(showFullLoader: false, passive: true),
    );
    _passiveRefresh.attach();
    _loadInbox();
  }

  @override
  void dispose() {
    _voice.removeListener(_onVoiceChanged);
    _voice.dispose();
    _intakeController.dispose();
    _passiveRefresh.dispose();
    super.dispose();
  }

  void _onVoiceChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  Future<void> _handleVoiceTranscript(String transcript) async {
    final trimmed = transcript.trim();
    if (trimmed.isEmpty) {
      return;
    }
    final current = _intakeController.text;
    if (current.isEmpty) {
      _intakeController.text = trimmed;
    } else {
      _intakeController.text = '$current $trimmed';
    }
    _intakeController.selection = TextSelection.collapsed(
      offset: _intakeController.text.length,
    );
  }

  bool get isIntakePending => _isIntakePending;

  Future<void> handleDroppedPaths(List<String> paths) async {
    if (_isIntakePending || paths.isEmpty) {
      return;
    }
    await _localIntakeActions.registerDroppedFiles(context, paths);
  }

  Future<void> _onLocalIntakeSuccess() async {
    await _loadInbox(showFullLoader: false);
  }

  Future<void> _loadInbox(
      {bool showFullLoader = true, bool passive = false}) async {
    if (!mounted) {
      return;
    }
    if (passive && _isSourceRefreshing) {
      return;
    }
    if (showFullLoader && !passive) {
      setState(() {
        _loadState = InboxLoadState.loading;
        _errorMessage = null;
      });
    }

    try {
      final snapshot = await widget.apiClient.getInbox();
      if (!mounted) {
        return;
      }
      setState(() {
        _inbox = snapshot;
        _loadState = InboxLoadState.ready;
        _refreshStatusMessage =
            SourceRefreshService.clearSyncContinuesMessageIfSettled(
          message: _refreshStatusMessage,
          statuses: snapshot.sourceSyncStatus,
        );
      });
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      if (passive && _inbox != null) {
        return;
      }
      setState(() {
        _loadState = InboxLoadState.error;
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
      if (_inbox == null) {
        _loadState = InboxLoadState.loading;
      }
    });
    try {
      final result = await _sourceRefreshService.refreshSources(
        timeout:
            widget.sourceRefreshTimeout ?? SourceRefreshService.defaultTimeout,
        pollInterval: widget.sourceRefreshPollInterval ??
            SourceRefreshService.pollInterval,
      );
      if (!mounted) {
        return;
      }
      if (result.timedOut) {
        setState(() {
          _refreshStatusMessage = SourceRefreshService.syncContinuesMessage;
        });
      }
      await _loadInbox(showFullLoader: _inbox == null);
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _refreshStatusMessage = e.message;
        if (_inbox == null) {
          _loadState = InboxLoadState.error;
          _errorMessage = e.message;
        }
      });
    } finally {
      if (mounted) {
        setState(() => _isSourceRefreshing = false);
      }
    }
  }

  Future<void> _submitIntake() async {
    if (_isIntakePending) {
      return;
    }
    final trimmed = _intakeController.text.trim();
    if (trimmed.isEmpty) {
      return;
    }
    setState(() {
      _isIntakePending = true;
      _intakeErrorMessage = null;
    });
    try {
      if (isExactHttpUrl(trimmed)) {
        final result = await widget.apiClient.intakeLink(trimmed);
        if (!mounted) {
          return;
        }
        _intakeController.clear();
        await _loadInbox(showFullLoader: false);
        if (!mounted) {
          return;
        }
        _showIntakeSnackBar(_intakeLinkSuccessMessage(result));
      } else {
        await widget.apiClient.captureNote(
          CaptureNoteRequest(text: _intakeController.text),
        );
        if (!mounted) {
          return;
        }
        _intakeController.clear();
        await _loadInbox(showFullLoader: false);
        if (!mounted) {
          return;
        }
        _showIntakeSnackBar('Заметка добавлена');
      }
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      setState(() => _intakeErrorMessage = e.message);
    } finally {
      if (mounted) {
        setState(() => _isIntakePending = false);
      }
    }
  }

  String _intakeLinkSuccessMessage(IntakeLinkResult result) {
    final contentStatus = result.contentStatus;
    if (contentStatus == 'ready') {
      if (result.status == 'unchanged') {
        return 'Содержимое уже проиндексировано';
      }
      return 'Добавлено, содержимое проиндексировано';
    }
  switch (contentStatus) {
      case 'pending':
        return 'Добавлено, содержимое обрабатывается';
      case 'metadata_only':
        return 'Добавлено только как метаданные';
      case 'unsupported':
        return 'Добавлено, но содержимое этого формата не индексируется';
      case 'too_large':
        return 'Добавлено, но файл слишком большой для индексации';
      case 'failed':
        return 'Добавлено, но индексация содержимого не удалась';
      default:
        break;
    }
    switch (result.status) {
      case 'updated':
        return 'Обновлено';
      case 'unchanged':
        return 'Уже добавлено';
      default:
        return 'Добавлено';
    }
  }

  void _showIntakeSnackBar(String message) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
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

  Future<void> _openSourceObject(InboxSourceObjectOut sourceObject) async {
    final result = await openObjectDetail(
      context,
      objectId: sourceObject.id,
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
    final inbox = _inbox;
    if (inbox == null) {
      return;
    }
    setState(() {
      _inbox = InboxOut(
        unresolvedNotifications: inbox.unresolvedNotifications,
        recentSourceObjects: inbox.recentSourceObjects
            .where((row) => row.id != result.deletedObjectId)
            .toList(),
        sourceSyncStatus: inbox.sourceSyncStatus,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return _wrapDropTarget(
      Column(
        children: [
          _buildIntakeBar(),
          if (_intakeErrorMessage != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(
                _intakeErrorMessage!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
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
          Expanded(
            child: Stack(
              children: [
                _buildBody(),
                if (_isDragHovering) const _DropOverlay(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _onVoicePressed() async {
    if (_voice.voiceState == VoiceState.recording) {
      await _voice.stopAndTranscribe();
      return;
    }
    if (_isIntakePending ||
        (_voice.isVoiceBusy && _voice.voiceState != VoiceState.recording)) {
      return;
    }
    if (_voice.voiceState == VoiceState.error) {
      _voice.clearError();
    }
    await _voice.startRecording();
  }

  Widget _buildIntakeBar() {
    final voiceBusy = _voice.isVoiceBusy;
    final inputDisabled = _isIntakePending || voiceBusy;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_voice.voiceState == VoiceState.recording)
            Material(
              color: Theme.of(context).colorScheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                child: Row(
                  children: [
                    const Icon(Icons.mic, size: 16),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Запись… нажмите микрофон, чтобы остановить',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          Row(
            children: [
              Expanded(
                child: TextField(
                  key: const Key('inbox_link_input'),
                  controller: _intakeController,
                  enabled: !inputDisabled,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    hintText: 'Введите заметку или вставьте ссылку',
                    isDense: true,
                    border: OutlineInputBorder(),
                  ),
                  onSubmitted: (_) => _submitIntake(),
                ),
              ),
              const SizedBox(width: 4),
              IconButton(
                key: const Key('inbox_voice_button'),
                visualDensity: VisualDensity.compact,
                tooltip: _voice.voiceState == VoiceState.recording
                    ? 'Остановить запись'
                    : 'Записать голос',
                onPressed: _isIntakePending &&
                        _voice.voiceState != VoiceState.recording
                    ? null
                    : _onVoicePressed,
                icon: _voice.voiceState == VoiceState.transcribing ||
                        _voice.voiceState == VoiceState.starting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Icon(
                        _voice.voiceState == VoiceState.recording
                            ? Icons.stop_circle_outlined
                            : Icons.mic_none_outlined,
                      ),
              ),
              const SizedBox(width: 4),
              FilledButton(
                key: const Key('inbox_link_add_button'),
                onPressed: inputDisabled ? null : _submitIntake,
                child: _isIntakePending
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Добавить'),
              ),
              IconButton(
                key: const Key('inbox_add_file_button'),
                tooltip: 'Добавить файл',
                onPressed: inputDisabled
                    ? null
                    : () => _localIntakeActions.pickAndRegisterFile(context),
                icon: const Icon(Icons.insert_drive_file_outlined),
              ),
              IconButton(
                key: const Key('inbox_add_folder_button'),
                tooltip: 'Добавить папку',
                onPressed: inputDisabled
                    ? null
                    : () => _localIntakeActions.pickAndRegisterFolder(context),
                icon: const Icon(Icons.folder_outlined),
              ),
            ],
          ),
          if (_voice.voiceState == VoiceState.error &&
              _voice.voiceErrorMessage != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                _voice.voiceErrorMessage!,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.error,
                  fontSize: 12,
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _wrapDropTarget(Widget child) {
    if (kIsWeb || !Platform.isLinux) {
      return child;
    }
    return DropTarget(
      onDragEntered: (_) {
        if (!mounted) {
          return;
        }
        setState(() => _isDragHovering = true);
      },
      onDragExited: (_) {
        if (!mounted) {
          return;
        }
        setState(() => _isDragHovering = false);
      },
      onDragDone: (detail) {
        if (!mounted) {
          return;
        }
        setState(() => _isDragHovering = false);
        final paths = detail.files
            .map((file) => file.path)
            .where((path) => path != null)
            .cast<String>()
            .toList();
        handleDroppedPaths(paths);
      },
      child: child,
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
        final syncErrorRows = sourceSyncErrorRows(inbox.sourceSyncStatus);
        if (!hasNotifications && !hasSources && syncErrorRows.isEmpty) {
          return const Center(child: Text('Входящие пусты'));
        }
        return ListView(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          children: [
            if (_refreshStatusMessage != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(_refreshStatusMessage!),
              ),
            SourceSyncErrorList(errorRows: syncErrorRows),
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
            const _SectionHeader(title: 'Последние входящие'),
            if (!hasSources)
              const Padding(
                padding: EdgeInsets.only(bottom: 8),
                child: Text('Нет недавних входящих объектов'),
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
                                origin: sourceObject.origin,
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

class _DropOverlay extends StatelessWidget {
  const _DropOverlay();

  @override
  Widget build(BuildContext context) {
    return Positioned.fill(
      child: IgnorePointer(
        child: Container(
          alignment: Alignment.center,
          color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.08),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            decoration: BoxDecoration(
              border: Border.all(
                color: Theme.of(context).colorScheme.primary,
                width: 2,
              ),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              'Перетащите файл или папку сюда',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
        ),
      ),
    );
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
            Text(
                'Приоритет: ${notificationPriorityLabel(notification.priority)}'),
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
    return Card(
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ObjectCompactHeaderRow(
                title: sourceObject.title,
                kind: sourceObject.kind,
                provider: sourceObject.provider,
                trailingText: when,
              ),
              if (sourceObject.excerpt != null)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(
                    sourceObject.excerpt!,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
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
