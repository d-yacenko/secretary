import 'package:flutter/material.dart';

import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../assistant/assistant_controller.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../navigation/secretary_navigation.dart';

class AssistantScreen extends StatefulWidget {
  const AssistantScreen({
    super.key,
    required this.controller,
    required this.apiClient,
    required this.authController,
    required this.captureController,
  });

  final AssistantController controller;
  final SecretaryApiClient apiClient;
  final AuthController authController;
  final CaptureController captureController;

  @override
  State<AssistantScreen> createState() => _AssistantScreenState();
}

class _AssistantScreenState extends State<AssistantScreen> {
  final _inputController = TextEditingController();
  final _scrollController = ScrollController();
  AssistantSendState? _lastSendState;

  @override
  void initState() {
    super.initState();
    _lastSendState = widget.controller.sendState;
    widget.controller.addListener(_onControllerChanged);
    if (widget.controller.pendingRetryMessage != null &&
        widget.controller.sendState == AssistantSendState.error) {
      _inputController.text = widget.controller.pendingRetryMessage!;
    }
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onControllerChanged);
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onControllerChanged() {
    if (mounted) {
      final controller = widget.controller;
      final pending = controller.pendingRetryMessage;
      if (pending != null &&
          controller.sendState == AssistantSendState.error &&
          _inputController.text != pending) {
        _inputController.text = pending;
        _inputController.selection = TextSelection.collapsed(offset: pending.length);
      }
      if (_lastSendState == AssistantSendState.sending &&
          controller.sendState == AssistantSendState.idle &&
          pending == null) {
        _inputController.clear();
      }
      _lastSendState = controller.sendState;
      setState(() {});
      _scrollToEnd();
    }
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) {
        return;
      }
      final target = _scrollController.position.maxScrollExtent;
      if (_scrollController.offset == target) {
        return;
      }
      _scrollController.jumpTo(target);
    });
  }

  Future<void> _send() async {
    final text = _inputController.text;
    await widget.controller.sendMessage(text);
    if (widget.controller.sendState != AssistantSendState.error) {
      _inputController.clear();
    }
  }

  Future<void> _onVoicePressed() async {
    final controller = widget.controller;
    if (controller.voiceState == AssistantVoiceState.recording) {
      await controller.stopVoiceRecordingAndTranscribe();
      return;
    }
    if (controller.isInputBlocked &&
        controller.voiceState != AssistantVoiceState.recording) {
      return;
    }
    if (controller.voiceState == AssistantVoiceState.error) {
      controller.clearVoiceError();
    }
    await controller.startVoiceRecording();
  }

  void _openReference(AssistantReference reference) {
    openObjectDetail(
      context,
      objectId: reference.objectId,
      apiClient: widget.apiClient,
      authController: widget.authController,
      captureController: widget.captureController,
      assistantController: widget.controller,
      onAskSecretary: (object) {
        widget.controller.setObjectContext(object);
      },
    );
  }

  String _affectedObjectsLabel(AssistantChatMessage message) {
    return 'Affected objects:';
  }

  void _openAffectedObject(AssistantAffectedObject affected) {
    openObjectDetail(
      context,
      objectId: affected.objectId,
      apiClient: widget.apiClient,
      authController: widget.authController,
      captureController: widget.captureController,
      assistantController: widget.controller,
      onAskSecretary: (object) {
        widget.controller.setObjectContext(object);
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final inputDisabled = controller.isInputBlocked;
    return Scaffold(
      body: Column(
        children: [
          if (controller.objectContext != null)
            _ContextBanner(
              label: 'Context: ${controller.objectContext!.displayLabel}',
              onClear: controller.clearObjectContext,
            ),
          if (controller.notificationContext != null)
            _ContextBanner(
              label: 'Context: ${controller.notificationContext!.displayLabel}',
              onClear: controller.clearNotificationContext,
            ),
          if (controller.voiceState == AssistantVoiceState.recording)
            Material(
              color: Theme.of(context).colorScheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Row(
                  children: [
                    const Icon(Icons.mic, size: 18),
                    const SizedBox(width: 8),
                    const Expanded(child: Text('Recording… tap microphone to stop')),
                    TextButton(
                      key: const Key('assistant_voice_stop'),
                      onPressed: controller.stopVoiceRecordingAndTranscribe,
                      child: const Text('Stop'),
                    ),
                  ],
                ),
              ),
            ),
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(16),
              itemCount: controller.messages.length,
              itemBuilder: (context, index) {
                final message = controller.messages[index];
                final isUser = message.role == 'user';
                final actionPlan = message.actionPlan;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Column(
                    crossAxisAlignment:
                        isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: isUser
                              ? Theme.of(context).colorScheme.primaryContainer
                              : Theme.of(context).colorScheme.surfaceContainerHighest,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(message.content),
                      ),
                      if (!isUser && actionPlan != null)
                        _ActionPlanCard(
                          actionPlan: actionPlan,
                          messageIndex: index,
                          controller: controller,
                          operationState: controller.actionPlanOperationState,
                        ),
                      if (!isUser && message.references.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 8),
                          child: Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: message.references
                                .map(
                                  (ref) => ActionChip(
                                    label: Text(ref.displayLabel),
                                    onPressed: () => _openReference(ref),
                                  ),
                                )
                                .toList(),
                          ),
                        ),
                      if (!isUser && message.affectedObjects.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 8),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                _affectedObjectsLabel(message),
                                style: Theme.of(context).textTheme.labelLarge,
                              ),
                              ...message.affectedObjects.map(
                                (affected) => ActionChip(
                                  label: Text(
                                    '${affected.kind}: ${affected.title} — ${affected.state}',
                                  ),
                                  onPressed: () => _openAffectedObject(affected),
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                );
              },
            ),
          ),
          if (controller.sendState == AssistantSendState.error &&
              controller.errorMessage != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  Expanded(child: Text(controller.errorMessage!)),
                  TextButton(onPressed: _send, child: const Text('Retry')),
                ],
              ),
            ),
          if (controller.voiceState == AssistantVoiceState.error &&
              controller.voiceErrorMessage != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  Expanded(child: Text(controller.voiceErrorMessage!)),
                  TextButton(
                    onPressed: inputDisabled ? null : _onVoicePressed,
                    child: const Text('Retry'),
                  ),
                ],
              ),
            ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    key: const Key('assistant_input'),
                    controller: _inputController,
                    minLines: 1,
                    maxLines: 4,
                    decoration: const InputDecoration(
                      hintText: 'Ask Secretary…',
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: inputDisabled ? null : (_) => _send(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  key: const Key('assistant_voice_button'),
                  tooltip: controller.voiceState == AssistantVoiceState.recording
                      ? 'Stop recording'
                      : 'Record voice command',
                  onPressed: inputDisabled &&
                          controller.voiceState != AssistantVoiceState.recording
                      ? null
                      : _onVoicePressed,
                  icon: controller.voiceState == AssistantVoiceState.transcribing ||
                          controller.voiceState == AssistantVoiceState.starting
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Icon(
                          controller.voiceState == AssistantVoiceState.recording
                              ? Icons.stop_circle_outlined
                              : Icons.mic_none_outlined,
                        ),
                ),
                FilledButton(
                  key: const Key('assistant_send_button'),
                  onPressed: inputDisabled ? null : _send,
                  child: controller.isSending
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Send'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ContextBanner extends StatelessWidget {
  const _ContextBanner({required this.label, required this.onClear});

  final String label;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.secondaryContainer,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(
          children: [
            Expanded(child: Text(label)),
            IconButton(
              tooltip: 'Remove context',
              onPressed: onClear,
              icon: const Icon(Icons.close),
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionPlanCard extends StatelessWidget {
  const _ActionPlanCard({
    required this.actionPlan,
    required this.messageIndex,
    required this.controller,
    required this.operationState,
  });

  final MessageActionPlan actionPlan;
  final int messageIndex;
  final AssistantController controller;
  final AssistantActionPlanOperationState operationState;

  @override
  Widget build(BuildContext context) {
    final cardState = actionPlan.cardState;
    final buttonsDisabled = controller.isActionPlanOperationBusy;

    String statusLabel;
    switch (cardState) {
      case ActionPlanCardState.pending:
        statusLabel = 'Requires confirmation';
      case ActionPlanCardState.completed:
        statusLabel = 'Completed';
      case ActionPlanCardState.rejected:
        statusLabel = 'Rejected';
      case ActionPlanCardState.failed:
        statusLabel = 'Failed';
      case ActionPlanCardState.expired:
        statusLabel = 'Expired';
    }

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                statusLabel,
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 8),
              ...actionPlan.plan.actions.map(
                (action) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(action.displayLabel),
                ),
              ),
              if (cardState == ActionPlanCardState.pending &&
                  controller.actionPlanErrorMessage != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    controller.actionPlanErrorMessage!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              if (cardState == ActionPlanCardState.pending)
                Row(
                  children: [
                    FilledButton(
                      key: Key('assistant_action_plan_approve_$messageIndex'),
                      onPressed: buttonsDisabled
                          ? null
                          : () => controller.approveActionPlanAt(messageIndex),
                      child: const Text('Approve'),
                    ),
                    const SizedBox(width: 8),
                    OutlinedButton(
                      key: Key('assistant_action_plan_reject_$messageIndex'),
                      onPressed: buttonsDisabled
                          ? null
                          : () => controller.rejectActionPlanAt(messageIndex),
                      child: const Text('Reject'),
                    ),
                  ],
                ),
              if (cardState == ActionPlanCardState.completed &&
                  actionPlan.resumeFailed)
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const SizedBox(height: 8),
                    const Text('Action completed.'),
                    const Text('Could not load Secretary\'s summary.'),
                    TextButton(
                      key: Key('assistant_action_plan_retry_$messageIndex'),
                      onPressed: buttonsDisabled
                          ? null
                          : () =>
                              controller.retryResumeSummary(actionPlan.plan.id),
                      child: const Text('Retry summary'),
                    ),
                  ],
                ),
            ],
          ),
        ),
      ),
    );
  }
}
