import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../assistant/voice_recorder.dart';
import '../assistant/voice_temp_files.dart';
import '../auth/auth_controller.dart';
import '../voice/voice_transcription_controller.dart';
import 'audioplayers_speech_player.dart';
import 'fake_speech_player.dart';
import 'speech_playback_controller.dart';
import 'speech_player.dart';
import 'voice_capture_diagnostics.dart';
import 'voice_confirmation.dart';
import 'voice_invocation_source.dart';
import 'voice_local_feedback.dart';
import 'voice_output_policy.dart';
import 'voice_output_policy_controller.dart';
import 'voice_turn_timing.dart';

const int maxAssistantHistoryMessages = 12;

const voiceUnsupportedPlanSpeech = 'Это действие нужно подтвердить на экране.';
const voiceRejectedSpeech = 'Не отправляю.';
const voiceExecutionFailedSpeech = 'Не удалось выполнить отправку.';
const voiceExpiredSpeech = 'Срок подтверждения истёк.';
const voiceResumeFailedSpeech =
    'Действие выполнено. Не удалось загрузить итоговый ответ секретаря.';
const voicePlanAmbiguousSpeech =
    'Нельзя подтвердить голосом: найдено несколько ожидающих действий.';
const voiceUnlockRequiredSpeech =
    'Нужно разблокировать устройство, чтобы подтвердить отправку.';

enum AssistantSendState { idle, sending, error }

enum AssistantVoiceState {
  idle,
  starting,
  recording,
  transcribing,
  thinking,
  speaking,
  error,
}

enum AssistantActionPlanOperationState {
  idle,
  approving,
  rejecting,
  resuming,
  error,
}

enum ActionPlanCardState { pending, completed, rejected, failed, expired }

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

class AssistantController extends ChangeNotifier {
  AssistantController({
    required SecretaryApiClient apiClient,
    required AuthController authController,
    VoiceRecorder? voiceRecorder,
    VoiceTempFiles? voiceTempFiles,
    VoiceTranscriptionController? voiceController,
    SpeechPlayer? speechPlayer,
    SpeechPlaybackController? speechPlayback,
    VoiceLocalFeedback? voiceFeedback,
    VoiceOutputPolicyController? voiceOutputPolicy,
    this.lockScreenSession = false,
  }) : _apiClient = apiClient,
       _authController = authController,
       _voiceTempFiles =
           voiceTempFiles ??
           (Platform.environment['FLUTTER_TEST'] == 'true'
               ? VoiceTempFiles(
                   directory: Directory.systemTemp.createTempSync(
                     'secretary_voice_test',
                   ),
                 )
               : VoiceTempFiles()) {
    _voice =
        voiceController ??
        VoiceTranscriptionController(
          apiClient: apiClient,
          authController: authController,
          voiceRecorder: voiceRecorder,
          voiceTempFiles: _voiceTempFiles,
        );
    _speech =
        speechPlayback ??
        SpeechPlaybackController(
          apiClient: apiClient,
          authController: authController,
          player:
              speechPlayer ??
              (Platform.environment['FLUTTER_TEST'] == 'true'
                  ? FakeSpeechPlayer()
                  : AudioplayersSpeechPlayer()),
          tempFiles: _voiceTempFiles,
        );
    _feedback =
        voiceFeedback ??
        (Platform.environment['FLUTTER_TEST'] == 'true'
            ? const NoopVoiceLocalFeedback()
            : AssetVoiceLocalFeedback());
    _voiceOutputPolicy =
        voiceOutputPolicy ??
        VoiceOutputPolicyController(authController: authController);
    _ownsVoiceOutputPolicy = voiceOutputPolicy == null;
    _voice.bindTranscriptConsumer(_handleVoiceTranscript);
    _voice.addListener(_onVoiceChanged);
    _voiceOutputPolicy.addListener(_onVoiceChanged);
    if (_ownsVoiceOutputPolicy) {
      _voiceOutputPolicy.attach();
    }
  }

  final SecretaryApiClient _apiClient;
  final AuthController _authController;
  late final VoiceTranscriptionController _voice;
  final VoiceTempFiles _voiceTempFiles;
  late final SpeechPlaybackController _speech;
  late final VoiceLocalFeedback _feedback;
  late final VoiceOutputPolicyController _voiceOutputPolicy;
  late final bool _ownsVoiceOutputPolicy;
  final bool lockScreenSession;

  bool keyguardLocked = false;
  bool lockScreenVoiceEnabled = false;

  VoiceOutputPolicyController get voiceOutputPolicy => _voiceOutputPolicy;

  bool get autoSpeechAllowed => _autoSpeechAllowed;

  VoiceInvocationSource get turnSource => _turnSource;

  bool get voiceInputActive => _voiceInputActive;

  bool get blocksExternalWrite => lockScreenSession && keyguardLocked;

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
  bool _voiceInputActive = false;
  bool _autoSpeechAllowed = false;
  VoiceInvocationSource _turnSource = VoiceInvocationSource.typed;
  bool _voiceApprovalArmed = false;
  bool _planNarrationInProgress = false;
  bool _speakingOverlay = false;
  String? _speechErrorMessage;
  bool _confirmationInFlight = false;
  InboxReviewReceipt? _pendingInboxReviewReceipt;

  AssistantVoiceState get voiceState {
    if (_speechErrorMessage != null) {
      return AssistantVoiceState.error;
    }
    if (_speakingOverlay || _speech.isSpeaking) {
      return AssistantVoiceState.speaking;
    }
    if (_voiceInputActive &&
        (sendState == AssistantSendState.sending ||
            isActionPlanOperationBusy)) {
      return AssistantVoiceState.thinking;
    }
    switch (_voice.voiceState) {
      case VoiceState.idle:
        return AssistantVoiceState.idle;
      case VoiceState.starting:
        return AssistantVoiceState.starting;
      case VoiceState.recording:
        return AssistantVoiceState.recording;
      case VoiceState.transcribing:
        return AssistantVoiceState.transcribing;
      case VoiceState.error:
        return AssistantVoiceState.error;
    }
  }

  String? get voiceErrorMessage =>
      _speechErrorMessage ?? _voice.voiceErrorMessage;

  List<AssistantChatMessage> get messages => List.unmodifiable(_messages);
  AssistantContextRef? get objectContext => _objectContext;
  AssistantContextRef? get notificationContext => _notificationContext;
  String? get pendingRetryMessage => _pendingRetryMessage;
  bool get isSending => sendState == AssistantSendState.sending;
  bool get isVoiceBusy => _voice.isVoiceBusy;
  bool get isSpeaking => _speakingOverlay || _speech.isSpeaking;
  bool get hasPendingActionPlan => _messages.any(
    (message) =>
        message.actionPlan != null &&
        message.actionPlan!.cardState == ActionPlanCardState.pending,
  );
  bool get isActionPlanOperationBusy =>
      actionPlanOperationState == AssistantActionPlanOperationState.approving ||
      actionPlanOperationState == AssistantActionPlanOperationState.rejecting ||
      actionPlanOperationState == AssistantActionPlanOperationState.resuming;
  bool get canSubmitOrdinaryAssistantMessage =>
      !isSending &&
      !isVoiceBusy &&
      !hasPendingActionPlan &&
      !isActionPlanOperationBusy &&
      !isSpeaking;
  bool get isInputBlocked => !canSubmitOrdinaryAssistantMessage;
  bool get canStartVoiceRecording {
    if (isActionPlanOperationBusy || _confirmationInFlight) {
      return false;
    }
    if (isSpeaking) {
      return true;
    }
    if (_voice.isVoiceBusy) {
      return false;
    }
    if (isSending) {
      return false;
    }
    if (hasPendingActionPlan) {
      return true;
    }
    return true;
  }

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

  Future<void> sendMessage(
    String text, {
    VoiceInvocationSource source = VoiceInvocationSource.typed,
    bool preserveTurn = false,
  }) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || !canSubmitOrdinaryAssistantMessage) {
      return;
    }

    if (!preserveTurn) {
      _beginTurn(source);
    }
    _voiceApprovalArmed = false;
    _planNarrationInProgress = false;
    sendState = AssistantSendState.sending;
    errorMessage = null;
    notifyListeners();

    final history = _boundedHistory();
    try {
      final started = Stopwatch()..start();
      final response = await _apiClient.sendAssistantMessage(
        AssistantMessageRequest(
          message: trimmed,
          history: history,
          contextObjectId: _objectContext?.id,
          contextNotificationId: _notificationContext?.id,
        ),
      );
      VoiceTurnTiming.interval('assistant_rtt_ms', started.elapsedMilliseconds);
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
      _pendingInboxReviewReceipt =
          _autoSpeechAllowed &&
              response.pendingActionPlan == null &&
              response.inboxReviewReceipt != null
          ? response.inboxReviewReceipt
          : null;
      if (_autoSpeechAllowed) {
        await _speakLatestAssistantResult();
      }
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
      errorMessage = localOpenAiDailyBudgetMessage(e) ?? e.message;
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
    if (blocksExternalWrite) {
      if (_autoSpeechAllowed) {
        await _speakDeterministic(voiceUnlockRequiredSpeech);
      }
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
        if (_autoSpeechAllowed) {
          await _speakDeterministic(voiceExecutionFailedSpeech);
        }
        return;
      }
      if (response.status == 'expired') {
        actionPlan.cardState = ActionPlanCardState.expired;
        actionPlanOperationState = AssistantActionPlanOperationState.idle;
        notifyListeners();
        if (_autoSpeechAllowed) {
          await _speakDeterministic(voiceExpiredSpeech);
        }
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
      actionPlanErrorMessage = localOpenAiDailyBudgetMessage(e) ?? e.message;
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
      _voiceApprovalArmed = false;
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      notifyListeners();
      if (_autoSpeechAllowed) {
        await _speakDeterministic(
          response.status == 'expired'
              ? voiceExpiredSpeech
              : voiceRejectedSpeech,
        );
      }
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
      actionPlanErrorMessage = localOpenAiDailyBudgetMessage(e) ?? e.message;
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
      if (_autoSpeechAllowed) {
        await _speakDeterministic(response.answer);
      }
    } on AuthenticationException catch (e) {
      actionPlan.resumeFailed = true;
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      actionPlanErrorMessage = e.message;
      _authController.handleAuthenticationFailure();
      notifyListeners();
      if (_autoSpeechAllowed) {
        await _speakDeterministic(voiceResumeFailedSpeech);
      }
    } on NetworkException catch (e) {
      actionPlan.resumeFailed = true;
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      actionPlanErrorMessage = e.message;
      notifyListeners();
      if (_autoSpeechAllowed) {
        await _speakDeterministic(voiceResumeFailedSpeech);
      }
    } on ApiException catch (e) {
      actionPlan.resumeFailed = true;
      actionPlanOperationState = AssistantActionPlanOperationState.idle;
      actionPlanErrorMessage = localOpenAiDailyBudgetMessage(e) ?? e.message;
      notifyListeners();
      if (_autoSpeechAllowed) {
        await _speakDeterministic(voiceResumeFailedSpeech);
      }
    }
  }

  /// Canonical Voice Assistant A trigger for on-screen mic and Android hardware.
  ///
  /// Idle/error: start recording. Recording: stop and transcribe. Speaking:
  /// stop TTS and start a new recording. Starting/transcribing/thinking: ignore.
  /// Pending Action Plan uses the existing confirmation utterance path.
  ///
  /// Audible cues never overlap an active microphone recording. Hands-free
  /// ready tone completes before the recorder starts. Stop cue plays after
  /// the recorder has stopped.
  Future<void> handleVoiceTrigger({
    VoiceInvocationSource source = VoiceInvocationSource.screenMic,
    bool startCueAlreadyPlayed = false,
    bool stopCueAlreadyPlayed = false,
  }) async {
    VoiceCaptureDiagnostics.trigger(source: source, state: voiceState.name);
    switch (voiceState) {
      case AssistantVoiceState.recording:
        await stopVoiceRecordingAndTranscribe(
          stopCueAlreadyPlayed: stopCueAlreadyPlayed,
        );
        return;
      case AssistantVoiceState.starting:
      case AssistantVoiceState.transcribing:
      case AssistantVoiceState.thinking:
        return;
      case AssistantVoiceState.speaking:
      case AssistantVoiceState.idle:
      case AssistantVoiceState.error:
        if (lockScreenSession && keyguardLocked && !lockScreenVoiceEnabled) {
          return;
        }
        VoiceTurnTiming.startTurn(
          startCueAlreadyPlayed ? 'native_or_assist' : 'ui',
        );
        VoiceCaptureDiagnostics.startTurn(
          turnId: '${DateTime.now().microsecondsSinceEpoch}-${source.name}',
          source: source,
        );
        final interruptedPlanNarration =
            voiceState == AssistantVoiceState.speaking &&
            _planNarrationInProgress;
        await stopSpeaking();
        if (interruptedPlanNarration) {
          _voiceApprovalArmed = false;
        }
        if (!startCueAlreadyPlayed) {
          await _feedback.playAck();
        }
        VoiceTurnTiming.mark('ack');
        VoiceCaptureDiagnostics.event('ack_completed');
        await startVoiceRecording(source: source);
        if (voiceState != AssistantVoiceState.recording) {
          return;
        }
        VoiceTurnTiming.mark('recording_ready');
        VoiceCaptureDiagnostics.event('recording_ready');
        return;
    }
  }

  Future<void> startVoiceRecording({
    VoiceInvocationSource source = VoiceInvocationSource.screenMic,
  }) async {
    if (voiceState == AssistantVoiceState.recording) {
      return;
    }
    if (!canStartVoiceRecording) {
      return;
    }
    if (isSpeaking) {
      final interruptedPlanNarration = _planNarrationInProgress;
      await stopSpeaking();
      if (interruptedPlanNarration) {
        _voiceApprovalArmed = false;
      }
    }
    if (voiceState == AssistantVoiceState.error) {
      clearVoiceError();
    }
    if (!hasPendingActionPlan) {
      _beginTurn(source);
    }
    await _voice.startRecording(
      beforeMicrophoneStart: () async {
        await _feedback.releasePlayback();
        if (!source.isHandsFree) {
          return;
        }
        VoiceTurnTiming.mark('ready_cue_requested');
        VoiceCaptureDiagnostics.event('ready_cue_requested');
        await _feedback.playReady();
        await _feedback.releasePlayback();
        VoiceTurnTiming.mark('ready_cue_completed');
        VoiceCaptureDiagnostics.event('ready_cue_completed');
      },
    );
  }

  Future<void> stopVoiceRecordingAndTranscribe({
    bool stopCueAlreadyPlayed = false,
  }) async {
    VoiceTurnTiming.mark('stop');
    VoiceCaptureDiagnostics.event('stop_trigger');
    await _voice.stopAndTranscribe(
      afterRecorderStopped: () async {
        VoiceTurnTiming.mark('stop_feedback');
        if (!stopCueAlreadyPlayed) {
          unawaited(_feedback.playStop());
        }
      },
    );
  }

  Future<void> stopSpeaking() async {
    _discardPendingInboxReviewCompletion();
    _planNarrationInProgress = false;
    _speakingOverlay = false;
    await _speech.stop();
    notifyListeners();
  }

  Future<void> _handleVoiceTranscript(String transcript) async {
    if (hasPendingActionPlan) {
      await _handleVoiceConfirmation(transcript);
      return;
    }
    if (!canSubmitOrdinaryAssistantMessage) {
      _pendingRetryMessage = transcript;
      notifyListeners();
      return;
    }
    await sendMessage(transcript, preserveTurn: true);
  }

  Future<void> _handleVoiceConfirmation(String transcript) async {
    if (_confirmationInFlight ||
        isActionPlanOperationBusy ||
        _approveInFlight) {
      return;
    }
    _confirmationInFlight = true;
    try {
      final pendingIndex = _uniquePendingPlanIndex();
      if (pendingIndex == null) {
        if (_autoSpeechAllowed) {
          await _speakDeterministic(voicePlanAmbiguousSpeech);
        }
        return;
      }
      final decision = parseVoiceConfirmation(transcript);
      if (decision == VoiceConfirmation.reject) {
        await rejectActionPlanAt(pendingIndex);
        return;
      }
      if (decision == VoiceConfirmation.approve) {
        if (blocksExternalWrite) {
          if (_autoSpeechAllowed) {
            await _speakDeterministic(voiceUnlockRequiredSpeech);
          }
          return;
        }
        final message = _messages[pendingIndex];
        final actions =
            message.actionPlan?.plan.actions ?? const <PendingAction>[];
        final voiceApprovable = PendingAction.planIsVoiceApprovable(actions);
        if (!_voiceApprovalArmed || !voiceApprovable) {
          if (_autoSpeechAllowed) {
            await _speakDeterministic(
              voiceApprovable
                  ? voiceApprovalUnarmedSpeech
                  : voiceUnsupportedPlanSpeech,
            );
          }
          return;
        }
        await approveActionPlanAt(pendingIndex);
        return;
      }
      if (_autoSpeechAllowed) {
        await _speakDeterministic(voiceConfirmationRetrySpeech);
      }
    } finally {
      _confirmationInFlight = false;
    }
  }

  int? _uniquePendingPlanIndex() {
    final indexes = <int>[];
    for (var i = 0; i < _messages.length; i++) {
      final plan = _messages[i].actionPlan;
      if (plan != null && plan.cardState == ActionPlanCardState.pending) {
        indexes.add(i);
      }
    }
    if (indexes.length == 1) {
      return indexes.first;
    }
    return null;
  }

  Future<void> _speakLatestAssistantResult() async {
    final pendingIndex = _uniquePendingPlanIndex();
    if (pendingIndex != null) {
      _discardPendingInboxReviewCompletion();
      if (blocksExternalWrite) {
        _voiceApprovalArmed = false;
        await _speakDeterministic(voiceUnlockRequiredSpeech);
        return;
      }
      final plan = _messages[pendingIndex].actionPlan!.plan;
      final preview = PendingAction.planVoicePreview(plan.actions);
      if (preview != null) {
        _voiceApprovalArmed = false;
        _planNarrationInProgress = true;
        await _speakDeterministic(preview, isPlanNarration: true);
        return;
      }
      _voiceApprovalArmed = false;
      final answer = _messages.last.content;
      final spoken = answer.trim().isEmpty
          ? voiceUnsupportedPlanSpeech
          : '$answer\n$voiceUnsupportedPlanSpeech';
      await _speakDeterministic(spoken);
      return;
    }
    await _speakDeterministic(_messages.last.content);
  }

  Future<void> _speakDeterministic(
    String text, {
    bool isPlanNarration = false,
  }) async {
    _speechErrorMessage = null;
    _speakingOverlay = true;
    notifyListeners();
    var playbackFinished = false;
    await _speech.speak(
      text,
      onFinished: () {
        playbackFinished = true;
        _speakingOverlay = false;
        if (isPlanNarration && _planNarrationInProgress) {
          _voiceApprovalArmed = true;
        }
        _planNarrationInProgress = false;
        notifyListeners();
      },
      onError: (message) {
        _discardPendingInboxReviewCompletion();
        _speakingOverlay = false;
        if (isPlanNarration) {
          _voiceApprovalArmed = false;
        }
        _planNarrationInProgress = false;
        _speechErrorMessage = message;
        notifyListeners();
      },
    );
    if (playbackFinished && !isPlanNarration) {
      await _completePendingInboxReviewAfterPlayback();
    }
  }

  void _discardPendingInboxReviewCompletion() {
    _pendingInboxReviewReceipt = null;
  }

  Future<void> _completePendingInboxReviewAfterPlayback() async {
    final receipt = _pendingInboxReviewReceipt;
    _pendingInboxReviewReceipt = null;
    if (receipt == null) {
      return;
    }
    try {
      await _apiClient.completeInboxReviewMarker(receipt);
    } catch (_) {
      // Fail closed: interrupted/errored/conflict completion must not move the marker.
    }
  }

  Future<void> cancelVoiceRecording() async {
    await _voice.cancel();
  }

  void clearVoiceError() {
    _speechErrorMessage = null;
    _voice.clearError();
    notifyListeners();
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

  void _beginTurn(VoiceInvocationSource source) {
    _discardPendingInboxReviewCompletion();
    _turnSource = source;
    _voiceInputActive = source.isVoiceInput;
    _autoSpeechAllowed =
        source.isHandsFree &&
        _voiceOutputPolicy.policy.allowsAutoSpeech(source);
    _voiceApprovalArmed = false;
    _planNarrationInProgress = false;
  }

  void resetSession() {
    _voice.reset();
    _speech.stop();
    _messages.clear();
    _objectContext = null;
    _notificationContext = null;
    sendState = AssistantSendState.idle;
    actionPlanOperationState = AssistantActionPlanOperationState.idle;
    errorMessage = null;
    actionPlanErrorMessage = null;
    _pendingRetryMessage = null;
    _approveInFlight = false;
    _voiceInputActive = false;
    _autoSpeechAllowed = false;
    _turnSource = VoiceInvocationSource.typed;
    _voiceApprovalArmed = false;
    _planNarrationInProgress = false;
    _speakingOverlay = false;
    _speechErrorMessage = null;
    _confirmationInFlight = false;
    _discardPendingInboxReviewCompletion();
    notifyListeners();
  }

  @override
  void dispose() {
    _voiceOutputPolicy.removeListener(_onVoiceChanged);
    if (_ownsVoiceOutputPolicy) {
      _voiceOutputPolicy.dispose();
    }
    _voice.removeListener(_onVoiceChanged);
    _voice.dispose();
    _speech.dispose();
    _feedback.dispose();
    super.dispose();
  }
}
