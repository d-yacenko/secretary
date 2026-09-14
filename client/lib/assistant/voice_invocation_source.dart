enum VoiceInvocationSource { typed, screenMic, hardwareButton, systemAssistant }

extension VoiceInvocationSourceHandsFree on VoiceInvocationSource {
  bool get isVoiceInput => this != VoiceInvocationSource.typed;

  bool get isHandsFree =>
      this == VoiceInvocationSource.hardwareButton ||
      this == VoiceInvocationSource.systemAssistant;
}
