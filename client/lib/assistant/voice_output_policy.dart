import 'voice_invocation_source.dart';

/// Device-local auto-speech preference. Not synced to UserSettings.
enum VoiceOutputPolicy {
  /// Speak only hands-free invocations (hardware / system assistant).
  handsFreeOnly,

  /// Speak after any microphone input, including the on-screen mic.
  allVoiceInput,

  /// Never auto-speak Assistant answers.
  never,
}

extension VoiceOutputPolicySpeech on VoiceOutputPolicy {
  bool allowsAutoSpeech(VoiceInvocationSource source) {
    switch (this) {
      case VoiceOutputPolicy.never:
        return false;
      case VoiceOutputPolicy.allVoiceInput:
        return source.isVoiceInput;
      case VoiceOutputPolicy.handsFreeOnly:
        return source.isHandsFree;
    }
  }
}
