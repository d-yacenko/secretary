import 'dart:async';

import 'package:audioplayers/audioplayers.dart';

import 'speech_player.dart';

/// Local-file playback via audioplayers (Android + Linux, minSdk 23 safe).
class AudioplayersSpeechPlayer implements SpeechPlayer {
  AudioplayersSpeechPlayer({AudioPlayer? player})
    : _player = player ?? AudioPlayer();

  final AudioPlayer _player;
  Completer<void>? _playDone;

  @override
  Future<void> playFile(String path) async {
    await stop();
    final done = Completer<void>();
    _playDone = done;
    late final StreamSubscription<void> completed;
    completed = _player.onPlayerComplete.listen((_) {
      if (!done.isCompleted) {
        done.complete();
      }
    });
    try {
      await _player.play(DeviceFileSource(path));
      await done.future;
    } finally {
      await completed.cancel();
      if (_playDone == done) {
        _playDone = null;
      }
    }
  }

  @override
  Future<void> stop() async {
    final pending = _playDone;
    await _player.stop();
    if (pending != null && !pending.isCompleted) {
      pending.complete();
    }
  }

  @override
  Future<void> dispose() async {
    await stop();
    await _player.dispose();
  }
}
