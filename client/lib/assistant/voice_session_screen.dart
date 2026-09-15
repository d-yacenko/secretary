import 'package:flutter/material.dart';

import 'assistant_controller.dart';
import 'system_assistant_bridge.dart';
import 'voice_invocation_source.dart';

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
  @override
  void initState() {
    super.initState();
    widget.assistant.addListener(_onChange);
    widget.systemAssistant.addListener(_onChange);
    widget.systemAssistant.onAssistInvoke = _onAssistInvoke;
    WidgetsBinding.instance.addPostFrameCallback((_) => _syncGate());
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

  Future<void> _syncGate() async {
    await widget.systemAssistant.refresh();
    _onChange();
  }

  void _onAssistInvoke() {
    widget.assistant.keyguardLocked = widget.systemAssistant.keyguardLocked;
    widget.assistant.lockScreenVoiceEnabled =
        widget.systemAssistant.lockScreenVoiceEnabled;
    widget.assistant.handleVoiceTrigger(
      source: VoiceInvocationSource.systemAssistant,
      startCueAlreadyPlayed: true,
    );
  }

  bool get _launcherEnabled => widget.systemAssistant.lockScreenVoiceEnabled;

  bool get _preparing {
    switch (widget.assistant.voiceState) {
      case AssistantVoiceState.starting:
      case AssistantVoiceState.transcribing:
      case AssistantVoiceState.thinking:
        return true;
      case AssistantVoiceState.idle:
      case AssistantVoiceState.recording:
      case AssistantVoiceState.speaking:
      case AssistantVoiceState.error:
        return false;
    }
  }

  String _statusText() {
    if (!_launcherEnabled) {
      return lockScreenVoiceEnabledMessage;
    }
    switch (widget.assistant.voiceState) {
      case AssistantVoiceState.starting:
        return 'Готовлюсь…';
      case AssistantVoiceState.recording:
        return 'Слушаю… Нажмите, чтобы остановить';
      case AssistantVoiceState.transcribing:
        return 'Распознаю…';
      case AssistantVoiceState.thinking:
        return 'Секретарь думает…';
      case AssistantVoiceState.speaking:
        return 'Секретарь говорит…';
      case AssistantVoiceState.error:
        return widget.assistant.voiceErrorMessage ?? 'Ошибка голоса';
      case AssistantVoiceState.idle:
        return 'Нажмите, чтобы говорить';
    }
  }

  String _buttonLabel() {
    switch (widget.assistant.voiceState) {
      case AssistantVoiceState.recording:
        return 'Стоп';
      case AssistantVoiceState.error:
        return 'Повторить';
      case AssistantVoiceState.speaking:
        return 'Прервать и говорить';
      case AssistantVoiceState.starting:
        return 'Готовлюсь…';
      case AssistantVoiceState.transcribing:
      case AssistantVoiceState.thinking:
        return 'Подождите…';
      case AssistantVoiceState.idle:
        return 'Нажмите, чтобы говорить';
    }
  }

  Future<void> _onLauncherTap() async {
    if (!_launcherEnabled || _preparing) {
      return;
    }
    await widget.assistant.handleVoiceTrigger(
      source: VoiceInvocationSource.lockScreenLauncher,
    );
  }

  @override
  Widget build(BuildContext context) {
    final assistant = widget.assistant;
    final theme = Theme.of(context);
    final recording = assistant.voiceState == AssistantVoiceState.recording;
    final color = recording
        ? theme.colorScheme.error
        : theme.colorScheme.primary;
    final onColor = recording
        ? theme.colorScheme.onError
        : theme.colorScheme.onPrimary;
    return Scaffold(
      backgroundColor: theme.colorScheme.surface,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Секретарь', style: theme.textTheme.titleLarge),
              const SizedBox(height: 16),
              Text(
                _statusText(),
                key: const Key('voice_session_status'),
                style: theme.textTheme.headlineSmall,
                textAlign: TextAlign.center,
              ),
              if (assistant.blocksExternalWrite) ...[
                const SizedBox(height: 16),
                Text(
                  voiceUnlockRequiredSpeech,
                  key: const Key('voice_session_unlock_required'),
                  textAlign: TextAlign.center,
                ),
              ],
              Expanded(
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    final side = constraints.biggest.shortestSide * 0.86;
                    return Center(
                      child: SizedBox(
                        width: side,
                        height: side,
                        child: Material(
                          color: _preparing
                              ? theme.colorScheme.surfaceContainerHighest
                              : color,
                          shape: const CircleBorder(),
                          child: InkWell(
                            key: const Key('voice_session_launcher_button'),
                            customBorder: const CircleBorder(),
                            onTap: (_launcherEnabled && !_preparing)
                                ? _onLauncherTap
                                : null,
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  recording
                                      ? Icons.stop_rounded
                                      : Icons.support_agent,
                                  size: side * 0.28,
                                  color: _preparing
                                      ? theme.colorScheme.onSurfaceVariant
                                      : onColor,
                                ),
                                const SizedBox(height: 16),
                                Padding(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 24,
                                  ),
                                  child: Text(
                                    _buttonLabel(),
                                    textAlign: TextAlign.center,
                                    style: theme.textTheme.titleLarge?.copyWith(
                                      color: _preparing
                                          ? theme.colorScheme.onSurfaceVariant
                                          : onColor,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
              TextButton(
                key: const Key('voice_session_close'),
                onPressed: widget.systemAssistant.dismissOverlay,
                child: const Text('Завершить режим вождения'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
