/// Cross-platform voice recording abstraction for short Assistant commands.
abstract class VoiceRecorder {
  Future<bool> hasPermission();

  Future<bool> requestPermission();

  Future<void> startRecording(String filePath);

  Future<String> stopRecording();

  Future<void> cancelRecording();

  Future<void> dispose();
}
