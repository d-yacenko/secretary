import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Network-independent START/STOP listening cues. Never persists files.
abstract class VoiceLocalFeedback {
  Future<void> playStart();

  Future<void> playStop();

  Future<void> dispose();
}

class NoopVoiceLocalFeedback implements VoiceLocalFeedback {
  const NoopVoiceLocalFeedback();

  @override
  Future<void> playStart() async {}

  @override
  Future<void> playStop() async {}

  @override
  Future<void> dispose() async {}
}

class RecordingVoiceLocalFeedback implements VoiceLocalFeedback {
  int startCount = 0;
  int stopCount = 0;

  @override
  Future<void> playStart() async {
    startCount += 1;
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
       _haptic = haptic ?? (() => HapticFeedback.mediumImpact());

  final AudioPlayer _player;
  final Future<void> Function() _haptic;
  bool _failed = false;

  @override
  Future<void> playStart() async {
    try {
      await _haptic();
    } catch (_) {}
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
