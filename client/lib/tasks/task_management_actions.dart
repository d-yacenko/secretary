import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';

class TaskManagementActions extends StatelessWidget {
  const TaskManagementActions({
    super.key,
    required this.task,
    required this.apiClient,
    required this.authController,
    required this.onTaskUpdated,
    this.compact = false,
  });

  final SecretaryObject task;
  final SecretaryApiClient apiClient;
  final AuthController authController;
  final ValueChanged<SecretaryObject> onTaskUpdated;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    if (task.kind != 'task' || task.isDeletedTask) {
      return const SizedBox.shrink();
    }

    final children = <Widget>[
      _actionButton(
        context,
        tooltip: 'Edit task',
        icon: Icons.edit_outlined,
        label: 'Edit',
        onPressed: () => _editTask(context),
      ),
      _actionButton(
        context,
        tooltip: 'Change status',
        icon: Icons.swap_horiz,
        label: 'Status',
        onPressed: () => _changeStatus(context),
      ),
      _actionButton(
        context,
        tooltip: 'Delete task',
        icon: Icons.delete_outline,
        label: 'Delete',
        onPressed: () => _deleteTask(context),
      ),
    ];

    if (compact) {
      return PopupMenuButton<String>(
        tooltip: 'Task actions',
        itemBuilder: (context) => [
          const PopupMenuItem(value: 'edit', child: Text('Edit')),
          const PopupMenuItem(value: 'status', child: Text('Change status')),
          const PopupMenuItem(value: 'delete', child: Text('Delete')),
        ],
        onSelected: (value) {
          switch (value) {
            case 'edit':
              _editTask(context);
            case 'status':
              _changeStatus(context);
            case 'delete':
              _deleteTask(context);
          }
        },
      );
    }

    return Wrap(spacing: 8, runSpacing: 8, children: children);
  }

  Widget _actionButton(
    BuildContext context, {
    required String tooltip,
    required IconData icon,
    required String label,
    required VoidCallback onPressed,
  }) {
    return Tooltip(
      message: tooltip,
      child: OutlinedButton.icon(
        onPressed: onPressed,
        icon: Icon(icon, size: 18),
        label: Text(label),
      ),
    );
  }

  Future<void> _editTask(BuildContext context) async {
    final titleController = TextEditingController(text: task.title);
    final bodyController = TextEditingController(text: task.body ?? '');
    DateTime? dueAt = task.dueAt == null ? null : DateTime.tryParse(task.dueAt!);
    final originalDueAt = dueAt;
    bool clearBody = false;
    bool clearDue = false;
    bool dueAtChanged = false;

    final saved = await showDialog<bool>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              title: const Text('Edit task'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: titleController,
                      decoration: const InputDecoration(labelText: 'Title'),
                    ),
                    TextField(
                      controller: bodyController,
                      decoration: const InputDecoration(labelText: 'Body'),
                      minLines: 2,
                      maxLines: 4,
                      enabled: !clearBody,
                    ),
                    CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Clear body'),
                      value: clearBody,
                      onChanged: (value) => setState(() => clearBody = value ?? false),
                    ),
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(
                        dueAt == null
                            ? 'No due date'
                            : dueAt!.toLocal().toString(),
                      ),
                      trailing: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          IconButton(
                            tooltip: 'Set due date',
                            onPressed: () async {
                              final pickedDate = await showDatePicker(
                                context: context,
                                initialDate: dueAt?.toLocal() ?? DateTime.now(),
                                firstDate: DateTime(2000),
                                lastDate: DateTime(2100),
                              );
                              if (pickedDate == null) {
                                return;
                              }
                              final pickedTime = await showTimePicker(
                                context: context,
                                initialTime: dueAt != null
                                    ? TimeOfDay.fromDateTime(dueAt!.toLocal())
                                    : TimeOfDay.now(),
                              );
                              if (pickedTime == null) {
                                return;
                              }
                              setState(() {
                                dueAt = DateTime(
                                  pickedDate.year,
                                  pickedDate.month,
                                  pickedDate.day,
                                  pickedTime.hour,
                                  pickedTime.minute,
                                );
                                clearDue = false;
                                dueAtChanged = true;
                              });
                            },
                            icon: const Icon(Icons.event_outlined),
                          ),
                          IconButton(
                            tooltip: 'Clear due date',
                            onPressed: () => setState(() {
                              clearDue = true;
                              dueAt = null;
                              dueAtChanged = true;
                            }),
                            icon: const Icon(Icons.event_busy_outlined),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(context, true),
                  child: const Text('Save'),
                ),
              ],
            );
          },
        );
      },
    );

    if (saved != true) {
      return;
    }

    final request = TaskPatchRequest();
    if (titleController.text.trim() != task.title) {
      request.title = titleController.text.trim();
      request.titleSet = true;
    }
    if (clearBody) {
      request.body = null;
      request.bodySet = true;
    } else if (bodyController.text != (task.body ?? '')) {
      request.body = bodyController.text;
      request.bodySet = true;
    }
    if (clearDue) {
      request.dueAt = null;
      request.dueAtSet = true;
    } else if (dueAtChanged && dueAt != null) {
      final newDueIso = dueAt!.toUtc().toIso8601String();
      final oldDueIso = originalDueAt?.toUtc().toIso8601String();
      if (newDueIso != oldDueIso) {
        request.dueAt = newDueIso;
        request.dueAtSet = true;
      }
    }

    if (request.isEmpty) {
      return;
    }

    try {
      final response = await apiClient.patchTask(task.id, request);
      onTaskUpdated(response.object);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Task updated')),
        );
      }
    } on AuthenticationException {
      authController.handleAuthenticationFailure();
    } on ApiException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    }
  }

  Future<void> _changeStatus(BuildContext context) async {
    final options = _statusOptionsFor(task.status);
    final selected = await showDialog<String>(
      context: context,
      builder: (context) => SimpleDialog(
        title: const Text('Change status'),
        children: options
            .map(
              (status) => SimpleDialogOption(
                onPressed: () => Navigator.pop(context, status),
                child: Text(status),
              ),
            )
            .toList(),
      ),
    );
    if (selected == null) {
      return;
    }
    try {
      final response = await apiClient.setTaskStatus(task.id, selected);
      onTaskUpdated(response.object);
    } on AuthenticationException {
      authController.handleAuthenticationFailure();
    } on ApiException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    }
  }

  Future<void> _deleteTask(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete task?'),
        content: Text(
          '${task.title}\n\nThis will hide the task from normal search and active views. '
          'Its graph history and relationships will be preserved.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) {
      return;
    }
    try {
      final response = await apiClient.softDeleteTask(task.id);
      onTaskUpdated(response.object);
    } on AuthenticationException {
      authController.handleAuthenticationFailure();
    } on ApiException catch (error) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    }
  }

  List<String> _statusOptionsFor(String? status) {
    switch (status) {
      case 'open':
      case null:
        return ['in_progress', 'done', 'cancelled', 'archived'];
      case 'in_progress':
        return ['open', 'done', 'cancelled', 'archived'];
      case 'done':
      case 'cancelled':
      case 'archived':
      case 'completed':
        return ['open'];
      default:
        return ['open', 'in_progress', 'done', 'cancelled', 'archived'];
    }
  }
}
