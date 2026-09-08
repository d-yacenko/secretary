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
import '../navigation/source_navigation_service.dart';
import '../ui/assigned_labels_loader.dart';
import '../ui/app_spacing.dart';
import '../ui/date_format.dart';
import '../ui/inbox_date_groups.dart';
import '../ui/object_actions.dart';
import '../ui/object_label_strip.dart';
import '../ui/object_presentation.dart';
import '../ui/passive_snapshot_refresh.dart';
import '../ui/provider_icon.dart';
import '../voice/voice_transcription_controller.dart';
import 'inbox_feed_merge.dart';
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
  List<InboxSourceObjectOut> _feedObjects = [];
  Map<String, List<LabelItem>> _labelsByObject = {};
  String? _errorMessage;
  String? _mutatingNotificationId;
  String? _refreshStatusMessage;
  String? _intakeErrorMessage;
  String? _nextCursor;
  String? _loadMoreError;
  bool _hasMore = false;
  bool _isLoadingMore = false;
  bool _loadedContinuation = false;
  bool _isSourceRefreshing = false;
  bool _isIntakePending = false;
  bool _isDragHovering = false;

  final TextEditingController _intakeController = TextEditingController();
  late final VoiceTranscriptionController _voice;

  late final SourceRefreshService _sourceRefreshService =
      SourceRefreshService(apiClient: widget.apiClient);
  late final SourceNavigationService _sourceNavigation =
      SourceNavigationService(apiClient: widget.apiClient);
  late final PassiveSnapshotRefresh _passiveRefresh;
  late final LocalIntakeActions _localIntakeActions;
  final ScrollController _feedScrollController = ScrollController();

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
    _feedScrollController.addListener(_onFeedScroll);
    _loadInbox();
  }

  @override
  void dispose() {
    _voice.removeListener(_onVoiceChanged);
    _voice.dispose();
    _intakeController.dispose();
    _feedScrollController.dispose();
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

  void _onFeedScroll() {
    if (!_feedScrollController.hasClients) {
      return;
    }
    if (_feedScrollController.position.extentAfter < 480) {
      _loadMore();
    }
  }

  void _scheduleFeedPrefetch() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        _onFeedScroll();
      }
    });
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
        _loadMoreError = null;
        _loadedContinuation = false;
      });
    }

    try {
      final snapshot = await widget.apiClient.getInbox();
      if (!mounted) {
        return;
      }
      final preserveTail = passive && _loadedContinuation;
      final mergedFeed = mergeInboxFeedHead(
        existing: _feedObjects,
        firstPage: snapshot.recentSourceObjects,
        preserveTail: preserveTail,
      );
      setState(() {
        _inbox = snapshot;
        _feedObjects = mergedFeed;
        if (!preserveTail) {
          _nextCursor = snapshot.recentNextCursor;
          _hasMore = snapshot.recentHasMore;
        }
        _loadState = InboxLoadState.ready;
        _refreshStatusMessage =
            SourceRefreshService.clearSyncContinuesMessageIfSettled(
          message: _refreshStatusMessage,
          statuses: snapshot.sourceSyncStatus,
        );
      });
      _scheduleFeedPrefetch();
      final labelIds = preserveTail
          ? snapshot.recentSourceObjects.map((item) => item.id)
          : mergedFeed.map((item) => item.id);
      final labels = await loadAssignedLabelsByObjects(
        apiClient: widget.apiClient,
        onAuthFailure: widget.authController.handleAuthenticationFailure,
        objectIds: labelIds,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        if (preserveTail) {
          _labelsByObject = {..._labelsByObject, ...labels};
        } else {
          _labelsByObject = labels;
        }
      });
      _scheduleFeedPrefetch();
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

  Future<void> _loadMore() async {
    if (_isLoadingMore || !_hasMore || _nextCursor == null) {
      return;
    }
    _isLoadingMore = true;
    setState(() {
      _loadMoreError = null;
    });
    final cursor = _nextCursor!;
    try {
      final page = await widget.apiClient.getInboxFeed(cursor: cursor);
      if (!mounted) {
        _isLoadingMore = false;
        return;
      }
      final known = _feedObjects.map((item) => item.id).toSet();
      final appended = [
        for (final item in page.items)
          if (!known.contains(item.id)) item,
      ];
      setState(() {
        _feedObjects = [..._feedObjects, ...appended];
        _nextCursor = page.nextCursor;
        _hasMore = page.hasMore;
        _isLoadingMore = false;
        _loadedContinuation = true;
      });
      _scheduleFeedPrefetch();
      if (appended.isEmpty) {
        return;
      }
      final labels = await loadAssignedLabelsByObjects(
        apiClient: widget.apiClient,
        onAuthFailure: widget.authController.handleAuthenticationFailure,
        objectIds: appended.map((item) => item.id),
      );
      if (!mounted) {
        return;
      }
      setState(() => _labelsByObject = {..._labelsByObject, ...labels});
    } on AuthenticationException {
      _isLoadingMore = false;
      if (mounted) {
        setState(() {});
      }
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      _isLoadingMore = false;
      if (!mounted) {
        return;
      }
      setState(() {
        _loadMoreError = e.message;
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
          recentNextCursor: inbox.recentNextCursor,
          recentHasMore: inbox.recentHasMore,
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
          recentNextCursor: inbox.recentNextCursor,
          recentHasMore: inbox.recentHasMore,
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

  Future<void> _openInboxSource(InboxSourceObjectOut sourceObject) async {
    try {
      await _sourceNavigation.launchForObject(sourceObject.id);
    } on SourceLaunchException catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.message)));
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.message)));
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
        recentNextCursor: inbox.recentNextCursor,
        recentHasMore: inbox.recentHasMore,
      );
      _feedObjects = _feedObjects
          .where((row) => row.id != result.deletedObjectId)
          .toList();
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
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
              child: Text(
                _intakeErrorMessage!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
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

  Widget _voiceButton() {
    return IconButton(
      key: const Key('inbox_voice_button'),
      visualDensity: VisualDensity.compact,
      tooltip: _voice.voiceState == VoiceState.recording
          ? 'Остановить запись'
          : 'Записать голос',
      padding: EdgeInsets.zero,
      constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
      style: IconButton.styleFrom(
        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
      ),
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
    );
  }

  List<Widget> _intakeSideButtons({required bool inputDisabled}) {
    return [
      Semantics(
        button: true,
        label: 'Добавить во входящие',
        child: Tooltip(
          message: 'Добавить во входящие',
          child: FilledButton(
            key: const Key('inbox_link_add_button'),
            onPressed: inputDisabled ? null : _submitIntake,
            style: FilledButton.styleFrom(
              minimumSize: const Size(40, 40),
              padding: const EdgeInsets.all(8),
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: _isIntakePending
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.move_to_inbox_outlined),
          ),
        ),
      ),
      IconButton(
        key: const Key('inbox_add_file_button'),
        tooltip: 'Добавить файл',
        visualDensity: VisualDensity.compact,
        onPressed: inputDisabled
            ? null
            : () => _localIntakeActions.pickAndRegisterFile(context),
        icon: const Icon(Icons.insert_drive_file_outlined),
      ),
      IconButton(
        key: const Key('inbox_add_folder_button'),
        tooltip: 'Добавить папку',
        visualDensity: VisualDensity.compact,
        onPressed: inputDisabled
            ? null
            : () => _localIntakeActions.pickAndRegisterFolder(context),
        icon: const Icon(Icons.folder_outlined),
      ),
      IconButton(
        key: const Key('inbox_refresh_button'),
        tooltip: 'Обновить',
        visualDensity: VisualDensity.compact,
        onPressed: _isSourceRefreshing ? null : _refreshWithSources,
        icon: _isSourceRefreshing
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : const Icon(Icons.refresh),
      ),
    ];
  }

  Widget _buildIntakeBar() {
    final voiceBusy = _voice.isVoiceBusy;
    final inputDisabled = _isIntakePending || voiceBusy;
    final wide = isWideLayout(context);
    final fieldEnabled = !_isIntakePending &&
        _voice.voiceState != VoiceState.starting &&
        _voice.voiceState != VoiceState.transcribing;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        AppSpacing.sm,
        AppSpacing.lg,
        0,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_voice.voiceState == VoiceState.recording)
            Material(
              color: Theme.of(context).colorScheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.md,
                  vertical: AppSpacing.xs,
                ),
                child: Row(
                  children: [
                    const Icon(Icons.mic, size: 16),
                    const SizedBox(width: AppSpacing.sm),
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
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: TextField(
                  key: const Key('inbox_link_input'),
                  controller: _intakeController,
                  enabled: fieldEnabled,
                  readOnly: _voice.voiceState == VoiceState.recording,
                  minLines: 1,
                  maxLines: wide ? 2 : 3,
                  decoration: InputDecoration(
                    hintText: 'Введите заметку или вставьте ссылку',
                    isDense: true,
                    border: const OutlineInputBorder(),
                    contentPadding: const EdgeInsets.fromLTRB(12, 10, 4, 10),
                    suffixIcon: _voiceButton(),
                    suffixIconConstraints: const BoxConstraints(
                      minWidth: 40,
                      minHeight: 36,
                    ),
                  ),
                  onSubmitted: (_) => _submitIntake(),
                ),
              ),
              if (wide) ...[
                const SizedBox(width: AppSpacing.xs),
                ..._intakeSideButtons(inputDisabled: inputDisabled),
              ],
            ],
          ),
          if (!wide)
            Padding(
              padding: const EdgeInsets.only(top: AppSpacing.xs),
              child: Wrap(
                spacing: AppSpacing.xs,
                runSpacing: AppSpacing.xs,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: _intakeSideButtons(inputDisabled: inputDisabled),
              ),
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
        final hasSources = _feedObjects.isNotEmpty;
        final syncErrorRows = sourceSyncErrorRows(inbox.sourceSyncStatus);
        if (!hasNotifications && !hasSources && syncErrorRows.isEmpty) {
          return const Center(child: Text('Входящие пусты'));
        }
        final groupedSources = groupInboxSourceEntries(_feedObjects);
        return ListView(
          key: const Key('inbox_feed_list'),
          controller: _feedScrollController,
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
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
              ...groupedSources.map(
                (entry) => switch (entry) {
                  InboxDateSeparatorEntry() => InboxDateSeparator(
                      entry: entry,
                    ),
                  InboxSourceObjectEntry(:final sourceObject) => Padding(
                      padding: EdgeInsets.only(
                        bottom: isWideLayout(context)
                            ? AppSpacing.xs
                            : AppSpacing.sm,
                      ),
                      child: _SourceObjectCard(
                        sourceObject: sourceObject,
                        labels: _labelsByObject[sourceObject.id] ?? const [],
                        onTap: () => _openSourceObject(sourceObject),
                        onOpenSource: providerHasIdentity(sourceObject.provider)
                            ? () => _openInboxSource(sourceObject)
                            : null,
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
                },
              ),
            if (_isLoadingMore)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Center(
                  child: SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
              ),
            if (_loadMoreError != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Column(
                  children: [
                    Text(
                      _loadMoreError!,
                      textAlign: TextAlign.center,
                    ),
                    TextButton(
                      key: const Key('inbox_load_more_retry'),
                      onPressed: _loadMore,
                      child: const Text('Повторить'),
                    ),
                  ],
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
    required this.labels,
    required this.onTap,
    this.onOpenSource,
    this.onAskSecretary,
    this.onShowInGraph,
  });

  final InboxSourceObjectOut sourceObject;
  final List<LabelItem> labels;
  final VoidCallback onTap;
  final VoidCallback? onOpenSource;
  final VoidCallback? onAskSecretary;
  final VoidCallback? onShowInGraph;

  @override
  Widget build(BuildContext context) {
    final when = formatUserDateTime(sourceObject.primaryAt);
    final feedDate = parseLocalInboxDate(sourceObject.feedStamp);
    final primaryDate = parseLocalInboxDate(sourceObject.primaryAt);
    final isEvent = sourceObject.kind == 'event' ||
        sourceObject.kind == 'calendar_event';
    final trailingTooltip = isEvent &&
            feedDate != null &&
            primaryDate != null &&
            feedDate != primaryDate
        ? 'Во входящих: ${formatInboxDateSeparator(feedDate)}; событие: $when'
        : null;
    final wide = isWideLayout(context);
    return Card(
      margin: EdgeInsets.zero,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: EdgeInsets.symmetric(
            horizontal: wide ? AppSpacing.md : AppSpacing.md,
            vertical: wide ? AppSpacing.xs : AppSpacing.sm,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ObjectCompactHeaderRow(
                title: sourceObject.title,
                kind: sourceObject.kind,
                provider: sourceObject.provider,
                trailingText: when,
                trailingTooltip: trailingTooltip,
                onProviderTap: onOpenSource,
              ),
              if (sourceObject.excerpt != null)
                Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.xs),
                  child: Text(
                    sourceObject.excerpt!,
                    maxLines: wide ? 1 : 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ObjectLabelStrip(labels: labels),
              if (onAskSecretary != null || onShowInGraph != null)
                Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.xs),
                  child: Wrap(
                    spacing: AppSpacing.xs,
                    children: [
                      if (onAskSecretary != null)
                        AskSecretaryAction(onPressed: onAskSecretary),
                      if (onShowInGraph != null)
                        OpenInGraphAction(onPressed: onShowInGraph),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
