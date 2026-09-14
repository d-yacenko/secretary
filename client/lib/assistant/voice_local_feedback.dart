import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Network-independent local Voice cues. Never persists files.
///
/// [playAck] means only "invocation recognized".
/// [playReady] means the recorder is actually running ("speak now").
/// [playStop] means stop / processing.
abstract class VoiceLocalFeedback {
  Future<void> playAck();

  Future<void> playReady();

  Future<void> playStop();

  Future<void> dispose();
}

class NoopVoiceLocalFeedback implements VoiceLocalFeedback {
  const NoopVoiceLocalFeedback();

  @override
  Future<void> playAck() async {}

  @override
  Future<void> playReady() async {}

  @override
  Future<void> playStop() async {}

  @override
  Future<void> dispose() async {}
}

class RecordingVoiceLocalFeedback implements VoiceLocalFeedback {
  int ackCount = 0;
  int readyCount = 0;
  int stopCount = 0;

  @override
  Future<void> playAck() async {
    ackCount += 1;
  }

  @override
  Future<void> playReady() async {
    readyCount += 1;
  }

  @override
  Future<void> playStop() async {
    stopCount += 1;
  }

  @override
  Future<void> dispose() async {}
}

class AssetVoiceLocalFeedback implements VoiceLocalFeedback {
  AssetVoiceLocalFeedback({
    AudioPlayer? player,
    Future<void> Function()? haptic,
  }) : _player = player ?? AudioPlayer(),
       _haptic = haptic ?? (() => HapticFeedback.lightImpact());

  final AudioPlayer _player;
  final Future<void> Function() _haptic;
  bool _failed = false;

  @override
  Future<void> playAck() async {
    try {
      await _haptic();
    } catch (_) {}
  }

  @override
  Future<void> playReady() async {
    await _play('sounds/voice_start.wav');
  }

  @override
  Future<void> playStop() async {
    await _play('sounds/voice_stop.wav');
  }

  Future<void> _play(String asset) async {
    if (_failed) {
      return;
    }
    try {
      await _player.stop();
      await _player.play(AssetSource(asset));
    } catch (error) {
      _failed = true;
      if (kDebugMode) {
        debugPrint('SecretaryVoiceTiming cue_failed ${error.runtimeType}');
      }
    }
  }

  @override
  Future<void> dispose() async {
    try {
      await _player.dispose();
    } catch (_) {}
  }
}
