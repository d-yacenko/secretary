import 'dart:async';
import 'dart:io';

import '../api/api_error.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';
import 'speech_player.dart';
import 'speech_text.dart';
import 'voice_temp_files.dart';

typedef SpeechPlaybackError = void Function(String message);

/// Sequential TTS request + local playback. Temp files are always deleted.
class SpeechPlaybackController {
  SpeechPlaybackController({
    required SecretaryApiClient apiClient,
    required AuthController authController,
    required SpeechPlayer player,
    required VoiceTempFiles tempFiles,
  }) : _apiClient = apiClient,
       _authController = authController,
       _player = player,
       _tempFiles = tempFiles;

  final SecretaryApiClient _apiClient;
  final AuthController _authController;
  final SpeechPlayer _player;
  final VoiceTempFiles _tempFiles;

  int _generation = 0;
  String? _activePath;
  bool _speaking = false;

  bool get isSpeaking => _speaking;

  Future<void> speak(
    String text, {
    required void Function() onFinished,
    required SpeechPlaybackError onError,
  }) async {
    final chunks = chunkSpeechText(text);
    if (chunks.isEmpty) {
      onFinished();
      return;
    }
    await speakChunks(chunks, onFinished: onFinished, onError: onError);
  }

  Future<void> speakChunks(
    List<String> chunks, {
    required void Function() onFinished,
    required SpeechPlaybackError onError,
  }) async {
    final generation = ++_generation;
    _speaking = true;
    try {
      for (final chunk in chunks) {
        if (generation != _generation) {
          return;
        }
        final bytes = await _apiClient.synthesizeSpeech(chunk);
        if (generation != _generation) {
          return;
        }
        final path = await _tempFiles.createTempAudioPath('mp3');
        await File(path).writeAsBytes(bytes, flush: true);
        if (generation != _generation) {
          await _tempFiles.deleteIfExists(path);
          return;
        }
        _activePath = path;
        try {
          await _player.playFile(path);
        } finally {
          await _tempFiles.deleteIfExists(path);
          if (_activePath == path) {
            _activePath = null;
          }
        }
      }
      if (generation == _generation) {
        _speaking = false;
        onFinished();
      }
    } on AuthenticationException catch (e) {
      if (generation == _generation) {
        _speaking = false;
        _authController.handleAuthenticationFailure();
        onError(e.message);
      }
    } on NetworkException catch (e) {
      if (generation == _generation) {
        _speaking = false;
        onError(e.message);
      }
    } on ApiException catch (e) {
      if (generation == _generation) {
        _speaking = false;
        onError(localOpenAiDailyBudgetMessage(e) ?? e.message);
      }
    } catch (_) {
      if (generation == _generation) {
        _speaking = false;
        onError('Не удалось озвучить ответ.');
      }
    }
  }

  Future<void> stop() async {
    _generation += 1;
    _speaking = false;
    await _player.stop();
    await _tempFiles.deleteIfExists(_activePath);
    _activePath = null;
  }

  Future<void> dispose() async {
    await stop();
    await _player.dispose();
  }
}
