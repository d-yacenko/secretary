import 'package:flutter/material.dart';

import 'capture_controller.dart';
import 'capture_draft.dart';

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key, required this.controller});

  final CaptureController controller;

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  late final TextEditingController _textController;
  late final TextEditingController _titleController;

  @override
  void initState() {
    super.initState();
    _textController = TextEditingController(text: widget.controller.draft.text);
    _titleController = TextEditingController(text: widget.controller.draft.title ?? '');
    widget.controller.addListener(_onControllerChanged);
  }

  void _onControllerChanged() {
    if (widget.controller.submitState == CaptureSubmitState.success &&
        widget.controller.draft.text.isEmpty) {
      _textController.clear();
      _titleController.clear();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Task created')),
        );
        widget.controller.clearSuccess();
      }
    }
    setState(() {});
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onControllerChanged);
    _textController.dispose();
    _titleController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final draft = controller.draft;
    final isSubmitting = controller.submitState == CaptureSubmitState.submitting;

    return Scaffold(
      appBar: AppBar(title: const Text('Capture task')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _textController,
              decoration: InputDecoration(
                labelText: 'Task text',
                hintText: 'What needs to be done?',
                errorText: draft.isTextTooLong
                    ? 'Text must be at most ${CaptureDraft.maxTextLength} characters'
                    : controller.submitState == CaptureSubmitState.validationError &&
                            draft.isBlank
                        ? 'Task text cannot be blank'
                        : null,
              ),
              maxLines: 8,
              maxLength: CaptureDraft.maxTextLength,
              onChanged: controller.setText,
              enabled: !isSubmitting,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _titleController,
              decoration: InputDecoration(
                labelText: 'Title (optional)',
                errorText: draft.isTitleTooLong
                    ? 'Title must be at most ${CaptureDraft.maxTitleLength} characters'
                    : null,
              ),
              maxLength: CaptureDraft.maxTitleLength,
              onChanged: controller.setTitle,
              enabled: !isSubmitting,
            ),
            if (controller.errorMessage != null &&
                controller.submitState != CaptureSubmitState.success)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  controller.errorMessage!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            if (draft.contextRefs.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text('Attached context', style: Theme.of(context).textTheme.labelLarge),
              const SizedBox(height: 4),
              ...draft.contextRefs.map(
                (ref) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text('Context attached: ${ref.title}'),
                ),
              ),
            ],
            const Spacer(),
            FilledButton(
              onPressed: draft.canSubmit && !isSubmitting ? controller.submit : null,
              child: isSubmitting
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Create task'),
            ),
          ],
        ),
      ),
    );
  }
}
