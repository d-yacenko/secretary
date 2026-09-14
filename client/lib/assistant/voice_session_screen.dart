import 'package:flutter/material.dart';

import 'assistant_controller.dart';
import 'system_assistant_bridge.dart';

class VoiceSessionScreen extends StatefulWidget {
  const VoiceSessionScreen({
    super.key,
    required this.assistant,
    required this.systemAssistant,
  });

  final AssistantController assistant;
  final SystemAssistantController systemAssistant;

  @override
  State<VoiceSessionScreen> createState() => _VoiceSessionScreenState();
}

class _VoiceSessionScreenState extends State<VoiceSessionScreen> {
  var _started = false;

  @override
  void initState() {
    super.initState();
    widget.assistant.addListener(_onChange);
    widget.systemAssistant.addListener(_onChange);
    widget.systemAssistant.onAssistInvoke = () {
      widget.assistant.handleVoiceTrigger(startCueAlreadyPlayed: true);
    };
    WidgetsBinding.instance.addPostFrameCallback((_) => _start());
  }

  @override
  void dispose() {
    widget.assistant.removeListener(_onChange);
    widget.systemAssistant.removeListener(_onChange);
    widget.systemAssistant.onAssistInvoke = null;
    super.dispose();
  }

  void _onChange() {
    widget.assistant.keyguardLocked = widget.systemAssistant.keyguardLocked;
    widget.assistant.lockScreenVoiceEnabled =
        widget.systemAssistant.lockScreenVoiceEnabled;
    if (mounted) {
      setState(() {});
    }
  }

  Future<void> _start() async {
    if (_started) {
      return;
    }
    _started = true;
    await widget.systemAssistant.refresh();
    widget.assistant.keyguardLocked = widget.systemAssistant.keyguardLocked;
    widget.assistant.lockScreenVoiceEnabled =
        widget.systemAssistant.lockScreenVoiceEnabled;
    if (widget.systemAssistant.keyguardLocked &&
        !widget.systemAssistant.lockScreenVoiceEnabled) {
      return;
    }
    await widget.assistant.handleVoiceTrigger(startCueAlreadyPlayed: true);
  }

  String _statusText() {
    if (widget.systemAssistant.keyguardLocked &&
        !widget.systemAssistant.lockScreenVoiceEnabled) {
      return lockScreenVoiceEnabledMessage;
    }
    switch (widget.assistant.voiceState) {
      case AssistantVoiceState.starting:
      case AssistantVoiceState.recording:
        return 'Слушаю…';
      case AssistantVoiceState.transcribing:
        return 'Распознаю…';
      case AssistantVoiceState.thinking:
        return 'Секретарь думает…';
      case AssistantVoiceState.speaking:
        return 'Секретарь говорит…';
      case AssistantVoiceState.error:
        return widget.assistant.voiceErrorMessage ?? 'Ошибка голоса';
      case AssistantVoiceState.idle:
        return 'Готово';
    }
  }

  @override
  Widget build(BuildContext context) {
    final assistant = widget.assistant;
    return Scaffold(
      backgroundColor: Theme.of(context).colorScheme.surface,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Секретарь', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 24),
              Text(
                _statusText(),
                key: const Key('voice_session_status'),
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              if (assistant.blocksExternalWrite) ...[
                const SizedBox(height: 16),
                Text(
                  voiceUnlockRequiredSpeech,
                  key: const Key('voice_session_unlock_required'),
                ),
              ],
              const Spacer(),
              if (assistant.voiceState == AssistantVoiceState.recording)
                FilledButton(
                  key: const Key('voice_session_stop'),
                  onPressed: assistant.stopVoiceRecordingAndTranscribe,
                  child: const Text('Стоп'),
                ),
              if (assistant.voiceState == AssistantVoiceState.speaking)
                OutlinedButton(
                  onPressed: assistant.stopSpeaking,
                  child: const Text('Стоп'),
                ),
              const SizedBox(height: 12),
              TextButton(
                key: const Key('voice_session_close'),
                onPressed: widget.systemAssistant.dismissOverlay,
                child: const Text('Закрыть'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
