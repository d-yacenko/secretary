import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';

import '../api/api_error.dart';
import '../api/secretary_api_client.dart';
import '../assistant/fake_voice_recorder.dart';
import '../assistant/record_voice_recorder.dart';
import '../assistant/voice_recorder.dart';
import '../assistant/voice_recorder_exceptions.dart';
import '../assistant/voice_temp_files.dart';
import '../auth/auth_controller.dart';

const Duration maxVoiceRecordingDuration = Duration(seconds: 60);

enum VoiceState {
  idle,
  starting,
  recording,
  transcribing,
  error,
}

class VoiceTranscriptionController extends ChangeNotifier {
  VoiceTranscriptionController({
    required SecretaryApiClient apiClient,
    required AuthController authController,
    VoiceRecorder? voiceRecorder,
    VoiceTempFiles? voiceTempFiles,
    Duration maxRecordingDuration = maxVoiceRecordingDuration,
    bool enableAutoStopInTests = false,
  })  : _apiClient = apiClient,
        _authController = authController,
        _voiceRecorder = voiceRecorder ??
            (Platform.environment['FLUTTER_TEST'] == 'true'
                ? FakeVoiceRecorder()
                : RecordVoiceRecorder()),
        _voiceTempFiles = voiceTempFiles ??
            (Platform.environment['FLUTTER_TEST'] == 'true'
                ? VoiceTempFiles(
                    directory: Directory.systemTemp
                        .createTempSync('secretary_voice_test'),
                  )
                : VoiceTempFiles()),
        _maxRecordingDuration = maxRecordingDuration,
        _enableAutoStopInTests = enableAutoStopInTests;

  final SecretaryApiClient _apiClient;
  final AuthController _authController;
  final VoiceRecorder _voiceRecorder;
  final VoiceTempFiles _voiceTempFiles;
  final Duration _maxRecordingDuration;
  final bool _enableAutoStopInTests;

  Future<void> Function(String transcript)? _transcriptConsumer;

  VoiceState voiceState = VoiceState.idle;
  String? voiceErrorMessage;
  String? _activeRecordingPath;
  Timer? _recordingLimitTimer;
  int _voiceStartGeneration = 0;
  bool _voiceStartInFlight = false;

  bool get isVoiceBusy =>
      _voiceStartInFlight ||
      voiceState == VoiceState.starting ||
      voiceState == VoiceState.recording ||
      voiceState == VoiceState.transcribing;

  void bindTranscriptConsumer(
    Future<void> Function(String transcript) consumer,
  ) {
    _transcriptConsumer = consumer;
  }

  Future<void> startRecording() async {
    if (_voiceStartInFlight) {
      return;
    }
    if (voiceState != VoiceState.idle && voiceState != VoiceState.error) {
      return;
    }

    if (voiceState == VoiceState.error) {
      voiceErrorMessage = null;
    }

    _voiceStartInFlight = true;
    voiceState = VoiceState.starting;
    final startGeneration = ++_voiceStartGeneration;
    String? operationPath;
    notifyListeners();

    try {
      final hasPermission = await _voiceRecorder.hasPermission();
      if (!hasPermission) {
        final granted = await _voiceRecorder.requestPermission();
        if (!granted) {
          if (!_isActiveVoiceStart(startGeneration)) {
            await _abortInFlightRecording(startGeneration, operationPath);
            return;
          }
          _setVoiceError(const VoiceRecorderPermissionDenied().message);
          return;
        }
      }

      if (!_isActiveVoiceStart(startGeneration)) {
        await _abortInFlightRecording(startGeneration, operationPath);
        return;
      }

      operationPath = await _voiceTempFiles.createTempAudioPath(
        _voiceRecorder.recordingFileExtension,
      );
      _activeRecordingPath = operationPath;
      await _voiceRecorder.startRecording(operationPath);

      if (!_isActiveVoiceStart(startGeneration)) {
        await _abortInFlightRecording(startGeneration, operationPath);
        return;
      }

      voiceState = VoiceState.recording;
      voiceErrorMessage = null;
      _recordingLimitTimer?.cancel();
      if (Platform.environment['FLUTTER_TEST'] != 'true' || _enableAutoStopInTests) {
        _recordingLimitTimer = Timer(_maxRecordingDuration, () {
          unawaited(stopAndTranscribe());
        });
      }
      notifyListeners();
    } on VoiceRecorderException catch (e) {
      if (_isActiveVoiceStart(startGeneration)) {
        await _cleanupRecordingPath(operationPath);
        _setVoiceError(e.message);
      } else {
        await _abortInFlightRecording(startGeneration, operationPath);
      }
    } catch (error) {
      if (kDebugMode) {
        debugPrint('Voice recording startup failed: ${error.runtimeType}');
      }
      if (_isActiveVoiceStart(startGeneration)) {
        await _cleanupRecordingPath(operationPath);
        _setVoiceError(const VoiceRecorderStartFailure().message);
      } else {
        await _abortInFlightRecording(startGeneration, operationPath);
      }
    } finally {
      _voiceStartInFlight = false;
      notifyListeners();
    }
  }

  Future<void> stopAndTranscribe({
    Future<void> Function(String transcript)? onTranscript,
  }) async {
    if (voiceState != VoiceState.recording) {
      return;
    }

    final handler = onTranscript ?? _transcriptConsumer;
    if (handler == null) {
      return;
    }

    voiceState = VoiceState.transcribing;
    voiceErrorMessage = null;
    _recordingLimitTimer?.cancel();
    _recordingLimitTimer = null;
    notifyListeners();

    String? recordedPath;
    try {
      recordedPath = await _voiceRecorder.stopRecording();
    } on VoiceRecorderException catch (e) {
      await _cleanupActiveRecording();
      _setVoiceError(e.message);
      return;
    } catch (_) {
      await _cleanupActiveRecording();
      _setVoiceError(const VoiceRecorderStopFailure().message);
      return;
    }
    _activeRecordingPath = null;

    final file = File(recordedPath);
    try {
      if (!await file.exists() || await file.length() == 0) {
        await _voiceTempFiles.deleteIfExists(recordedPath);
        _setVoiceError(const VoiceRecorderStopFailure().message);
        return;
      }
    } catch (_) {
      await _voiceTempFiles.deleteIfExists(recordedPath);
      _setVoiceError(const VoiceRecorderStopFailure().message);
      return;
    }

    List<int> audioBytes;
    try {
      audioBytes = await file.readAsBytes();
    } catch (_) {
      await _voiceTempFiles.deleteIfExists(recordedPath);
      _setVoiceError(const VoiceRecorderStopFailure().message);
      return;
    } finally {
      await _voiceTempFiles.deleteIfExists(recordedPath);
    }

    try {
      final transcript = await _apiClient.transcribeAudio(
        audioBytes: audioBytes,
        filename: _voiceRecorder.recordingFilename,
        contentType: _voiceRecorder.recordingContentType,
      );
      voiceState = VoiceState.idle;
      notifyListeners();
      await handler(transcript);
    } on AuthenticationException catch (e) {
      voiceState = VoiceState.error;
      voiceErrorMessage = e.message;
      _authController.handleAuthenticationFailure();
      notifyListeners();
    } on NetworkException catch (e) {
      _setVoiceError(e.message);
    } on ApiException catch (e) {
      _setVoiceError(e.message);
    }
  }

  Future<void> cancel() async {
    if (voiceState == VoiceState.starting) {
      _invalidateVoiceStart();
      voiceState = VoiceState.idle;
      voiceErrorMessage = null;
      notifyListeners();
      return;
    }
    if (voiceState != VoiceState.recording) {
      return;
    }

    _recordingLimitTimer?.cancel();
    _recordingLimitTimer = null;

    await _bestEffortCancelRecorder();
    await _cleanupActiveRecording();
    _resetVoiceToIdle();
    notifyListeners();
  }

  void clearError() {
    if (voiceState == VoiceState.error) {
      voiceState = VoiceState.idle;
      voiceErrorMessage = null;
      notifyListeners();
    }
  }

  void reset() {
    if (voiceState == VoiceState.starting ||
        voiceState == VoiceState.recording) {
      _invalidateVoiceStart();
      _recordingLimitTimer?.cancel();
      _recordingLimitTimer = null;
      if (voiceState == VoiceState.recording) {
        unawaited(_bestEffortCancelRecorder());
        unawaited(_cleanupActiveRecording());
      }
    }
    voiceState = VoiceState.idle;
    voiceErrorMessage = null;
    notifyListeners();
  }

  void _setVoiceError(String message) {
    voiceState = VoiceState.error;
    voiceErrorMessage = message;
    notifyListeners();
  }

  void _resetVoiceToIdle() {
    voiceState = VoiceState.idle;
    voiceErrorMessage = null;
  }

  bool _isActiveVoiceStart(int generation) =>
      generation == _voiceStartGeneration;

  void _invalidateVoiceStart() {
    _voiceStartGeneration++;
  }

  Future<void> _abortInFlightRecording(
    int generation,
    String? operationPath,
  ) async {
    if (generation != _voiceStartGeneration) {
      await _bestEffortCancelRecorder();
      await _cleanupRecordingPath(operationPath);
    }
    if (voiceState == VoiceState.starting ||
        voiceState == VoiceState.recording) {
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

  Future<void> _cleanupRecordingPath(String? path) async {
    if (path == null || path.isEmpty) {
      return;
    }
    await _voiceTempFiles.deleteIfExists(path);
    if (_activeRecordingPath == path) {
      _activeRecordingPath = null;
    }
  }

  Future<void> _cleanupActiveRecording() async {
    await _cleanupRecordingPath(_activeRecordingPath);
  }

  @override
  void dispose() {
    _recordingLimitTimer?.cancel();
    if (voiceState == VoiceState.recording ||
        voiceState == VoiceState.starting) {
      _invalidateVoiceStart();
      final path = _activeRecordingPath;
      _activeRecordingPath = null;
      voiceState = VoiceState.idle;
      unawaited(_bestEffortCancelRecorder());
      unawaited(_voiceTempFiles.deleteIfExists(path));
    }
    unawaited(_voiceRecorder.dispose());
    super.dispose();
  }
}
