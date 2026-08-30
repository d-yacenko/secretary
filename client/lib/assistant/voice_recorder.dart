/// Cross-platform voice recording abstraction for short Assistant commands.
abstract class VoiceRecorder {
  /// File extension for the active recording format (without dot).
  String get recordingFileExtension => 'wav';

  /// MIME type matching [recordingFileExtension].
  String get recordingContentType => 'audio/wav';

  /// Upload filename for transcription.
  String get recordingFilename => 'secretary_voice.$recordingFileExtension';

  Future<bool> hasPermission();

  Future<bool> requestPermission();

  Future<void> startRecording(String filePath);

  Future<String> stopRecording();

  Future<void> cancelRecording();

  Future<void> dispose();
}
