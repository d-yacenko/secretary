import 'dart:io';

import 'voice_recorder.dart';
import 'voice_recorder_exceptions.dart';

/// Deterministic recorder for tests without microphone access.
class FakeVoiceRecorder implements VoiceRecorder {
  FakeVoiceRecorder({List<int>? audioBytes}) {
    _audioBytes = audioBytes ?? [0, 1, 2, 3, 4];
  }

  bool permissionGranted = true;
  bool requestPermissionResult = true;
  bool failStart = false;
  bool failStartAfterWrite = false;
  bool failStop = false;
  bool throwOnHasPermission = false;
  bool throwOnRequestPermission = false;
  bool throwEncoderUnsupported = false;
  bool isRecording = false;
  String? lastStartedPath;
  int startCallCount = 0;
  int stopCallCount = 0;
  int cancelCallCount = 0;
  Duration startDelay = Duration.zero;
  Duration stopDelay = Duration.zero;

  late List<int> _audioBytes;
  String _extension = 'wav';
  String _contentType = 'audio/wav';

  @override
  String get recordingFileExtension => _extension;

  @override
  String get recordingContentType => _contentType;

  @override
  String get recordingFilename => 'secretary_voice.$_extension';

  set recordingFileExtension(String value) => _extension = value;

  set recordingContentType(String value) => _contentType = value;

  @override
  Future<bool> hasPermission() async {
    if (throwOnHasPermission) {
      throw StateError('permission check failed');
    }
    return permissionGranted;
  }

  @override
  Future<bool> requestPermission() async {
    if (throwOnRequestPermission) {
      throw StateError('permission request failed');
    }
    permissionGranted = requestPermissionResult;
    return requestPermissionResult;
  }

  @override
  Future<void> startRecording(String filePath) async {
    if (throwEncoderUnsupported) {
      throw const VoiceRecorderEncoderUnsupported();
    }
    startCallCount += 1;
    lastStartedPath = filePath;
    if (startDelay > Duration.zero) {
      await Future<void>.delayed(startDelay);
    }
    await File(filePath).writeAsBytes(_audioBytes);
    if (failStartAfterWrite) {
      throw StateError('recording start failed after write');
    }
    if (failStart) {
      throw StateError('recording start failed');
    }
    isRecording = true;
  }

  @override
  Future<String> stopRecording() async {
    stopCallCount += 1;
    if (stopDelay > Duration.zero) {
      await Future<void>.delayed(stopDelay);
    }
    if (failStop) {
      throw StateError('recording stop failed');
    }
    isRecording = false;
    if (lastStartedPath == null) {
      throw StateError('no active recording');
    }
    return lastStartedPath!;
  }

  @override
  Future<void> cancelRecording() async {
    cancelCallCount += 1;
    isRecording = false;
    if (lastStartedPath != null) {
      final file = File(lastStartedPath!);
      if (await file.exists()) {
        await file.delete();
      }
    }
  }

  @override
  Future<void> dispose() async {}
}
