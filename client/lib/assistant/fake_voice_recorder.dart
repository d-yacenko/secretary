import 'dart:io';

import 'voice_recorder.dart';

/// Deterministic recorder for tests without microphone access.
class FakeVoiceRecorder implements VoiceRecorder {
  FakeVoiceRecorder({List<int>? audioBytes}) {
    _audioBytes = audioBytes ?? [0, 1, 2, 3, 4];
  }

  bool permissionGranted = true;
  bool requestPermissionResult = true;
  bool failStart = false;
  bool failStop = false;
  bool isRecording = false;
  String? lastStartedPath;
  int startCallCount = 0;
  int stopCallCount = 0;
  int cancelCallCount = 0;

  late List<int> _audioBytes;

  @override
  Future<bool> hasPermission() async => permissionGranted;

  @override
  Future<bool> requestPermission() async {
    permissionGranted = requestPermissionResult;
    return requestPermissionResult;
  }

  @override
  Future<void> startRecording(String filePath) async {
    startCallCount += 1;
    if (failStart) {
      throw StateError('recording start failed');
    }
    isRecording = true;
    lastStartedPath = filePath;
    await File(filePath).writeAsBytes(_audioBytes);
  }

  @override
  Future<String> stopRecording() async {
    stopCallCount += 1;
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
