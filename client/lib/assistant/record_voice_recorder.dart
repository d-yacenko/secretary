import 'package:record/record.dart';

import 'voice_recorder.dart';

/// Production voice recorder backed by the `record` Flutter package.
class RecordVoiceRecorder implements VoiceRecorder {
  RecordVoiceRecorder() : _recorder = AudioRecorder();

  final AudioRecorder _recorder;

  static const RecordConfig _config = RecordConfig(
    encoder: AudioEncoder.wav,
    sampleRate: 16000,
    numChannels: 1,
  );

  @override
  Future<bool> hasPermission() => _recorder.hasPermission();

  @override
  Future<bool> requestPermission() => _recorder.hasPermission();

  @override
  Future<void> startRecording(String filePath) async {
    if (!await _recorder.isEncoderSupported(_config.encoder)) {
      throw StateError('WAV encoder is not supported on this platform');
    }
    await _recorder.start(_config, path: filePath);
  }

  @override
  Future<String> stopRecording() async {
    final path = await _recorder.stop();
    if (path == null || path.isEmpty) {
      throw StateError('Recording stopped without a file path');
    }
    return path;
  }

  @override
  Future<void> cancelRecording() async {
    await _recorder.cancel();
  }

  @override
  Future<void> dispose() async {
    await _recorder.dispose();
  }
}
