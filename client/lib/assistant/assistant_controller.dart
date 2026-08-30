import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';
import 'fake_voice_recorder.dart';
import 'record_voice_recorder.dart';
import 'voice_recorder.dart';
import 'voice_temp_files.dart';

const int maxAssistantHistoryMessages = 12;
const Duration maxVoiceRecordingDuration = Duration(seconds: 60);

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

class AssistantChatMessage {
  AssistantChatMessage({
    required this.role,
    required this.content,
    this.references = const [],
    this.affectedObjects = const [],
  });

  final String role;
  final String content;
  final List<AssistantReference> references;
  final List<AssistantAffectedObject> affectedObjects;
}

class AssistantController extends ChangeNotifier {
  AssistantController({
    required SecretaryApiClient apiClient,
    required AuthController authController,
    VoiceRecorder? voiceRecorder,
    VoiceTempFiles? voiceTempFiles,
  })  : _apiClient = apiClient,
        _authController = authController,
        _voiceRecorder = voiceRecorder ??
            (Platform.environment['FLUTTER_TEST'] == 'true'
                ? FakeVoiceRecorder()
                : RecordVoiceRecorder()),
        _voiceTempFiles = voiceTempFiles ?? VoiceTempFiles();

  final SecretaryApiClient _apiClient;
  final AuthController _authController;
  final VoiceRecorder _voiceRecorder;
  final VoiceTempFiles _voiceTempFiles;

  final List<AssistantChatMessage> _messages = [];
  AssistantContextRef? _objectContext;
  AssistantContextRef? _notificationContext;
  AssistantSendState sendState = AssistantSendState.idle;
  AssistantVoiceState voiceState = AssistantVoiceState.idle;
  String? errorMessage;
  String? voiceErrorMessage;
  String? _pendingRetryMessage;
  String? _activeRecordingPath;
  Timer? _recordingLimitTimer;
  int _voiceStartGeneration = 0;

  List<AssistantChatMessage> get messages => List.unmodifiable(_messages);
  AssistantContextRef? get objectContext => _objectContext;
  AssistantContextRef? get notificationContext => _notificationContext;
  String? get pendingRetryMessage => _pendingRetryMessage;
  bool get isSending => sendState == AssistantSendState.sending;
  bool get isVoiceBusy =>
      voiceState == AssistantVoiceState.starting ||
      voiceState == AssistantVoiceState.recording ||
      voiceState == AssistantVoiceState.transcribing;

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
    if (trimmed.isEmpty ||
        sendState == AssistantSendState.sending ||
        isVoiceBusy) {
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

  Future<void> startVoiceRecording() async {
    if (voiceState != AssistantVoiceState.idle &&
        voiceState != AssistantVoiceState.error) {
      return;
    }
    if (sendState == AssistantSendState.sending) {
      return;
    }

    if (voiceState == AssistantVoiceState.error) {
      voiceErrorMessage = null;
    }

    voiceState = AssistantVoiceState.starting;
    final startGeneration = ++_voiceStartGeneration;
    notifyListeners();

    try {
      final hasPermission = await _voiceRecorder.hasPermission();
      if (!hasPermission) {
        final granted = await _voiceRecorder.requestPermission();
        if (!granted) {
          if (!_isActiveVoiceStart(startGeneration)) {
            await _abortInFlightRecording(startGeneration);
            return;
          }
          _setVoiceError('Microphone permission is required for voice input.');
          return;
        }
      }

      if (!_isActiveVoiceStart(startGeneration)) {
        await _abortInFlightRecording(startGeneration);
        return;
      }

      final path = await _voiceTempFiles.createTempWavPath();
      _activeRecordingPath = path;
      await _voiceRecorder.startRecording(path);

      if (!_isActiveVoiceStart(startGeneration)) {
        await _abortInFlightRecording(startGeneration);
        return;
      }

      voiceState = AssistantVoiceState.recording;
      voiceErrorMessage = null;
      _recordingLimitTimer?.cancel();
      if (Platform.environment['FLUTTER_TEST'] != 'true') {
        _recordingLimitTimer = Timer(maxVoiceRecordingDuration, () {
          unawaited(stopVoiceRecordingAndTranscribe());
        });
      }
      notifyListeners();
    } catch (_) {
      if (_isActiveVoiceStart(startGeneration)) {
        await _cleanupActiveRecording();
        _setVoiceError('Voice recording could not start.');
      } else {
        await _abortInFlightRecording(startGeneration);
      }
    }
  }

  Future<void> stopVoiceRecordingAndTranscribe() async {
    if (voiceState != AssistantVoiceState.recording) {
      return;
    }

    voiceState = AssistantVoiceState.transcribing;
    voiceErrorMessage = null;
    _recordingLimitTimer?.cancel();
    _recordingLimitTimer = null;
    notifyListeners();

    String? recordedPath;
    try {
      recordedPath = await _voiceRecorder.stopRecording();
    } catch (_) {
      await _cleanupActiveRecording();
      _setVoiceError('Voice recording failed.');
      return;
    }
    _activeRecordingPath = null;

    final file = File(recordedPath);
    try {
      if (!await file.exists() || await file.length() == 0) {
        await _voiceTempFiles.deleteIfExists(recordedPath);
        _setVoiceError('Voice recording failed.');
        return;
      }
    } catch (_) {
      await _voiceTempFiles.deleteIfExists(recordedPath);
      _setVoiceError('Voice recording failed.');
      return;
    }

    List<int> audioBytes;
    try {
      audioBytes = await file.readAsBytes();
    } catch (_) {
      await _voiceTempFiles.deleteIfExists(recordedPath);
      _setVoiceError('Voice recording failed.');
      return;
    } finally {
      await _voiceTempFiles.deleteIfExists(recordedPath);
    }

    try {
      final transcript = await _apiClient.transcribeAudio(
        audioBytes: audioBytes,
        filename: 'secretary_voice.wav',
        contentType: 'audio/wav',
      );
      voiceState = AssistantVoiceState.idle;
      notifyListeners();
      if (sendState == AssistantSendState.sending) {
        _pendingRetryMessage = transcript;
        notifyListeners();
        return;
      }
      await sendMessage(transcript);
    } on AuthenticationException catch (e) {
      voiceState = AssistantVoiceState.error;
      voiceErrorMessage = e.message;
      _authController.handleAuthenticationFailure();
      notifyListeners();
    } on NetworkException catch (e) {
      _setVoiceError(e.message);
    } on ApiException catch (e) {
      _setVoiceError(e.message);
    }
  }

  Future<void> cancelVoiceRecording() async {
    if (voiceState == AssistantVoiceState.starting) {
      _invalidateVoiceStart();
      voiceState = AssistantVoiceState.idle;
      voiceErrorMessage = null;
      notifyListeners();
      return;
    }
    if (voiceState != AssistantVoiceState.recording) {
      return;
    }

    _recordingLimitTimer?.cancel();
    _recordingLimitTimer = null;

    await _bestEffortCancelRecorder();
    await _cleanupActiveRecording();
    _resetVoiceToIdle();
    notifyListeners();
  }

  void clearVoiceError() {
    if (voiceState == AssistantVoiceState.error) {
      voiceState = AssistantVoiceState.idle;
      voiceErrorMessage = null;
      notifyListeners();
    }
  }

  void _setVoiceError(String message) {
    voiceState = AssistantVoiceState.error;
    voiceErrorMessage = message;
    notifyListeners();
  }

  void _resetVoiceToIdle() {
    voiceState = AssistantVoiceState.idle;
    voiceErrorMessage = null;
  }

  bool _isActiveVoiceStart(int generation) =>
      generation == _voiceStartGeneration;

  void _invalidateVoiceStart() {
    _voiceStartGeneration++;
  }

  Future<void> _abortInFlightRecording(int generation) async {
    if (generation != _voiceStartGeneration) {
      await _bestEffortCancelRecorder();
      await _cleanupActiveRecording();
    }
    if (voiceState == AssistantVoiceState.starting ||
        voiceState == AssistantVoiceState.recording) {
      _resetVoiceToIdle();
      notifyListeners();
    }
  }

  Future<void> _bestEffortCancelRecorder() async {
    try {
      await _voiceRecorder.cancelRecording();
    } catch (_) {
      // Best-effort cleanup only.
    }
  }

  Future<void> _cleanupActiveRecording() async {
    final path = _activeRecordingPath;
    _activeRecordingPath = null;
    await _voiceTempFiles.deleteIfExists(path);
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
    if (voiceState == AssistantVoiceState.starting ||
        voiceState == AssistantVoiceState.recording) {
      _invalidateVoiceStart();
      _recordingLimitTimer?.cancel();
      _recordingLimitTimer = null;
      if (voiceState == AssistantVoiceState.recording) {
        unawaited(_bestEffortCancelRecorder());
        unawaited(_cleanupActiveRecording());
      }
    }
    _messages.clear();
    _objectContext = null;
    _notificationContext = null;
    sendState = AssistantSendState.idle;
    voiceState = AssistantVoiceState.idle;
    errorMessage = null;
    voiceErrorMessage = null;
    _pendingRetryMessage = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _recordingLimitTimer?.cancel();
    if (voiceState == AssistantVoiceState.recording ||
        voiceState == AssistantVoiceState.starting) {
      _invalidateVoiceStart();
      final path = _activeRecordingPath;
      _activeRecordingPath = null;
      voiceState = AssistantVoiceState.idle;
      unawaited(_bestEffortCancelRecorder());
      unawaited(_voiceTempFiles.deleteIfExists(path));
    }
    unawaited(_voiceRecorder.dispose());
    super.dispose();
  }
}
