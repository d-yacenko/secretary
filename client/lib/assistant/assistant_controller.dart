import 'package:flutter/foundation.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../assistant/voice_recorder.dart';
import '../assistant/voice_temp_files.dart';
import '../auth/auth_controller.dart';
import '../voice/voice_transcription_controller.dart';

const int maxAssistantHistoryMessages = 12;

enum AssistantSendState {
  idle,
  sending,
  error,
}

enum AssistantVoiceState {
  idle,
  starting,
  recording,
  transcribing,
  error,
}

enum AssistantActionPlanOperationState {
  idle,
  approving,
  rejecting,
  resuming,
  error,
}

enum ActionPlanCardState {
  pending,
  completed,
  rejected,
  failed,
  expired,
}

class MessageActionPlan {
  MessageActionPlan({
    required this.plan,
    this.cardState = ActionPlanCardState.pending,
    this.resumeFailed = false,
  });

  final PendingActionPlan plan;
  ActionPlanCardState cardState;
  bool resumeFailed;
}

class AssistantChatMessage {
  AssistantChatMessage({
    required this.role,
    required this.content,
    this.references = const [],
    this.affectedObjects = const [],
    this.actionPlan,
  });

  final String role;
  final String content;
  final List<AssistantReference> references;
  final List<AssistantAffectedObject> affectedObjects;
  final MessageActionPlan? actionPlan;
}

AssistantVoiceState _mapVoiceState(VoiceState state) =>
    AssistantVoiceState.values[state.index];

class AssistantController extends ChangeNotifier {
  AssistantController({
    required SecretaryApiClient apiClient,
    required AuthController authController,
    VoiceRecorder? voiceRecorder,
    VoiceTempFiles? voiceTempFiles,
    VoiceTranscriptionController? voiceController,
  })  : _apiClient = apiClient,
        _authController = authController,
        _voice = voiceController ??
            VoiceTranscriptionController(
              apiClient: apiClient,
              authController: authController,
              voiceRecorder: voiceRecorder,
              voiceTempFiles: voiceTempFiles,
            ) {
    _voice.bindTranscriptConsumer(_handleVoiceTranscript);
    _voice.addListener(_onVoiceChanged);
  }

  final SecretaryApiClient _apiClient;
  final AuthController _authController;
  final VoiceTranscriptionController _voice;

  final List<AssistantChatMessage> _messages = [];
  AssistantContextRef? _objectContext;
  AssistantContextRef? _notificationContext;
  AssistantSendState sendState = AssistantSendState.idle;
  AssistantActionPlanOperationState actionPlanOperationState =
      AssistantActionPlanOperationState.idle;
  String? errorMessage;
  String? actionPlanErrorMessage;
  String? _pendingRetryMessage;
  bool _approveInFlight = false;

  AssistantVoiceState get voiceState => _mapVoiceState(_voice.voiceState);
  String? get voiceErrorMessage => _voice.voiceErrorMessage;

  List<AssistantChatMessage> get messages => List.unmodifiable(_messages);
  AssistantContextRef? get objectContext => _objectContext;
  AssistantContextRef? get notificationContext => _notificationContext;
  String? get pendingRetryMessage => _pendingRetryMessage;
  bool get isSending => sendState == AssistantSendState.sending;
  bool get isVoiceBusy => _voice.isVoiceBusy;
  bool get hasPendingActionPlan => _messages.any(
        (message) =>
            message.actionPlan != null &&
            message.actionPlan!.cardState == ActionPlanCardState.pending,
      );
  bool get isActionPlanOperationBusy =>
      actionPlanOperationState == AssistantActionPlanOperationState.approving ||
      actionPlanOperationState == AssistantActionPlanOperationState.rejecting ||
      actionPlanOperationState == AssistantActionPlanOperationState.resuming;
  bool get isInputBlocked =>
      isSending ||
      isVoiceBusy ||
      hasPendingActionPlan ||
      isActionPlanOperationBusy;

  void _onVoiceChanged() {
    notifyListeners();
  }

  void setObjectContext(SecretaryObject object) {
    _objectContext = AssistantContextRef(
      id: object.id,
      title: object.title,
      kind: object.kind,
    );
    _notificationContext = null;
    notifyListeners();
  }

  void setNotificationContext(NotificationOut notification) {
    _notificationContext = AssistantContextRef(
      id: notification.id,
      title: notification.title,
      kind: 'notification',
    );
    _objectContext = null;
    notifyListeners();
  }

  void clearObjectContext() {
    _objectContext = null;
    notifyListeners();
  }

  void clearNotificationContext() {
    _notificationContext = null;
    notifyListeners();
  }

  Future<void> sendMessage(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || isInputBlocked) {
      return;
    }

    sendState = AssistantSendState.sending;
    errorMessage = null;
    notifyListeners();

    final history = _boundedHistory();
    try {
      final response = await _apiClient.sendAssistantMessage(
        AssistantMessageRequest(
          message: trimmed,
          history: history,
          contextObjectId: _objectContext?.id,
          contextNotificationId: _notificationContext?.id,
        ),
      );
      _messages.add(AssistantChatMessage(role: 'user', content: trimmed));
      _messages.add(
        AssistantChatMessage(
          role: 'assistant',
          content: response.answer,
          references: response.references,
          affectedObjects: response.affectedObjects,
          actionPlan: response.pendingActionPlan == null
              ? null
              : MessageActionPlan(plan: response.pendingActionPlan!),
        ),
      );
      _pendingRetryMessage = null;
      sendState = AssistantSendState.idle;
      notifyListeners();
    } on AuthenticationException catch (e) {
      _pendingRetryMessage = trimmed;
      sendState = AssistantSendState.error;
      errorMessage = e.message;
      _authController.handleAuthenticationFailure();
      notifyListeners();
    } on NetworkException catch (e) {
      _pendingRetryMessage = trimmed;
      sendState = AssistantSendState.error;
      errorMessage = e.message;
      notifyListeners();
    } on ApiException catch (e) {
      _pendingRetryMessage = trimmed;
      sendState = AssistantSendState.error;
      errorMessage = e.message;
      notifyListeners();
    }
  }

  Future<void> approveActionPlanAt(int messageIndex) async {
    if (_approveInFlight ||
        actionPlanOperationState != AssistantActionPlanOperationState.idle) {
      return;
    }
    if (messageIndex < 0 || messageIndex >= _messages.length) {
      return;
    }
    final message = _messages[messageIndex];
    final actionPlan = message.actionPlan;
    if (actionPlan == null ||
        actionPlan.cardState != ActionPlanCardState.pending) {
      return;
    }

    _approveInFlight = true;
    actionPlanOperationState = AssistantActionPlanOperationState.approving;
    actionPlanErrorMessage = null;
    notifyListeners();

    try {
      final response = await _apiClient.approveActionPlan(actionPlan.plan.id);
      if (response.status == 'failed') {
        actionPlan.cardState = ActionPlanCardState.failed;
        actionPlanOperationState = AssistantActionPlanOperationState.idle;
        notifyListeners();
        return;
      }
      if (response.status == 'expired') {
        actionPlan.cardState = ActionPlanCardState.expired;
        actionPlanOperationState = AssistantActionPlanOperationState.idle;
        notifyListeners();
        return;
      }
      if (response.status == 'executed') {
        actionPlan.cardState = ActionPlanCardState.completed;
        actionPlan.resumeFailed = false;
        notifyListeners();
        await _resumeExecutedPlan(actionPlan);
        return;
      }
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      notifyListeners();
    } on AuthenticationException catch (e) {
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      actionPlanErrorMessage = e.message;
      _authController.handleAuthenticationFailure();
      notifyListeners();
    } on NetworkException catch (e) {
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      actionPlanErrorMessage = e.message;
      notifyListeners();
    } on ApiException catch (e) {
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      actionPlanErrorMessage = e.message;
      notifyListeners();
    } finally {
      _approveInFlight = false;
    }
  }

  Future<void> rejectActionPlanAt(int messageIndex) async {
    if (actionPlanOperationState != AssistantActionPlanOperationState.idle) {
      return;
    }
    if (messageIndex < 0 || messageIndex >= _messages.length) {
      return;
    }
    final message = _messages[messageIndex];
    final actionPlan = message.actionPlan;
    if (actionPlan == null ||
        actionPlan.cardState != ActionPlanCardState.pending) {
      return;
    }

    actionPlanOperationState = AssistantActionPlanOperationState.rejecting;
    actionPlanErrorMessage = null;
    notifyListeners();

    try {
      final response = await _apiClient.rejectActionPlan(actionPlan.plan.id);
      if (response.status == 'expired') {
        actionPlan.cardState = ActionPlanCardState.expired;
      } else {
        actionPlan.cardState = ActionPlanCardState.rejected;
      }
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      notifyListeners();
    } on AuthenticationException catch (e) {
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      actionPlanErrorMessage = e.message;
      _authController.handleAuthenticationFailure();
      notifyListeners();
    } on NetworkException catch (e) {
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      actionPlanErrorMessage = e.message;
      notifyListeners();
    } on ApiException catch (e) {
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      actionPlanErrorMessage = e.message;
      notifyListeners();
    }
  }

  Future<void> retryResumeSummary(String planId) async {
    if (actionPlanOperationState != AssistantActionPlanOperationState.idle) {
      return;
    }
    MessageActionPlan? actionPlan;
    for (final message in _messages) {
      final candidate = message.actionPlan;
      if (candidate != null &&
          candidate.plan.id == planId &&
          candidate.cardState == ActionPlanCardState.completed) {
        actionPlan = candidate;
        break;
      }
    }
    if (actionPlan == null) {
      return;
    }
    await _resumeExecutedPlan(actionPlan);
  }

  Future<void> _resumeExecutedPlan(MessageActionPlan actionPlan) async {
    actionPlanOperationState = AssistantActionPlanOperationState.resuming;
    actionPlanErrorMessage = null;
    notifyListeners();

    try {
      final response = await _apiClient.resumeActionPlan(actionPlan.plan.id);
      _messages.add(
        AssistantChatMessage(
          role: 'assistant',
          content: response.answer,
          affectedObjects: response.affectedObjects,
        ),
      );
      actionPlan.resumeFailed = false;
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      notifyListeners();
    } on AuthenticationException catch (e) {
      actionPlan.resumeFailed = true;
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      actionPlanErrorMessage = e.message;
      _authController.handleAuthenticationFailure();
      notifyListeners();
    } on NetworkException catch (e) {
      actionPlan.resumeFailed = true;
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      actionPlanErrorMessage = e.message;
      notifyListeners();
    } on ApiException catch (e) {
      actionPlan.resumeFailed = true;
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      actionPlanErrorMessage = e.message;
      notifyListeners();
    }
  }

  Future<void> startVoiceRecording() async {
    if (isInputBlocked) {
      return;
    }
    if (voiceState == AssistantVoiceState.error) {
      clearVoiceError();
    }
    await _voice.startRecording();
  }

  Future<void> stopVoiceRecordingAndTranscribe() async {
    await _voice.stopAndTranscribe();
  }

  Future<void> _handleVoiceTranscript(String transcript) async {
    if (isInputBlocked) {
      _pendingRetryMessage = transcript;
      notifyListeners();
      return;
    }
    await sendMessage(transcript);
  }

  Future<void> cancelVoiceRecording() async {
    await _voice.cancel();
  }

  void clearVoiceError() {
    _voice.clearError();
  }

  List<AssistantHistoryMessage> _boundedHistory() {
    final pairs = <AssistantHistoryMessage>[];
    for (final message in _messages) {
      pairs.add(
        AssistantHistoryMessage(role: message.role, content: message.content),
      );
    }
    if (pairs.length > maxAssistantHistoryMessages) {
      return pairs.sublist(pairs.length - maxAssistantHistoryMessages);
    }
    return pairs;
  }

  void resetSession() {
    _voice.reset();
    _messages.clear();
    _objectContext = null;
    _notificationContext = null;
    sendState = AssistantSendState.idle;
    actionPlanOperationState = AssistantActionPlanOperationState.idle;
    errorMessage = null;
    actionPlanErrorMessage = null;
    _pendingRetryMessage = null;
    _approveInFlight = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _voice.removeListener(_onVoiceChanged);
    _voice.dispose();
    super.dispose();
  }
}
