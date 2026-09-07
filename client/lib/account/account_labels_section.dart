import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';
import 'account_layout.dart';

String labelConflictMessage(ApiException error) {
  final raw = error.message.toLowerCase();
  if (raw.contains('already exists')) {
    return 'Метка с таким именем уже существует.';
  }
  return error.message;
}

class AccountLabelsSection extends StatefulWidget {
  const AccountLabelsSection({
    super.key,
    required this.apiClient,
    required this.authController,
  });

  final SecretaryApiClient apiClient;
  final AuthController authController;

  @override
  State<AccountLabelsSection> createState() => _AccountLabelsSectionState();
}

class _AccountLabelsSectionState extends State<AccountLabelsSection> {
  List<LabelItem> _labels = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await widget.apiClient.listLabels();
      if (!mounted) {
        return;
      }
      setState(() {
        _labels = result.labels;
        _loading = false;
      });
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loading = false;
        _error = e.message;
      });
    }
  }

  void _upsert(LabelItem label) {
    final next = [..._labels];
    final index = next.indexWhere((item) => item.id == label.id);
    if (index >= 0) {
      next[index] = label;
    } else {
      next.add(label);
    }
    next.sort((a, b) => a.title.toLowerCase().compareTo(b.title.toLowerCase()));
    setState(() => _labels = next);
  }

  Future<void> _create() async {
    final name = await showLabelNameDialog(context, title: 'Создать метку');
    if (name == null || !mounted) {
      return;
    }
    try {
      final result = await widget.apiClient.createLabel(name);
      if (!mounted) {
        return;
      }
      _upsert(result.label);
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(labelConflictMessage(e))),
      );
    }
  }

  Future<void> _rename(LabelItem label) async {
    final name = await showLabelNameDialog(
      context,
      title: 'Переименовать метку',
      initial: label.title,
      submitLabel: 'Сохранить',
    );
    if (name == null || !mounted) {
      return;
    }
    try {
      final result = await widget.apiClient.renameLabel(
        labelId: label.id,
        name: name,
      );
      if (!mounted) {
        return;
      }
      _upsert(result.label);
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(labelConflictMessage(e))),
      );
    }
  }

  Future<void> _delete(LabelItem label) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Удалить метку?'),
        content: const Text(
          'Метка будет удалена из Секретаря.\n'
          'Объекты и данные источников удалены не будут.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Отмена'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Удалить'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) {
      return;
    }
    try {
      await widget.apiClient.deleteLabel(label.id);
      if (!mounted) {
        return;
      }
      setState(() {
        _labels = _labels.where((item) => item.id != label.id).toList();
      });
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return AccountSectionCard(
      title: 'Метки',
      children: [
        if (_loading)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Center(child: CircularProgressIndicator()),
          )
        else if (_error != null)
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
              const SizedBox(height: 8),
              TextButton(onPressed: _load, child: const Text('Повторить')),
            ],
          )
        else ...[
          if (_labels.isEmpty)
            Text(
              'Нет меток',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          for (final label in _labels)
            ListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              title: Text(label.title),
              subtitle: Text('объектов: ${label.objectCount}'),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    tooltip: 'Переименовать',
                    icon: const Icon(Icons.edit_outlined),
                    onPressed: () => _rename(label),
                  ),
                  IconButton(
                    tooltip: 'Удалить',
                    icon: const Icon(Icons.delete_outline),
                    onPressed: () => _delete(label),
                  ),
                ],
              ),
            ),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              key: const Key('account_create_label'),
              onPressed: _create,
              icon: const Icon(Icons.add),
              label: const Text('Создать метку'),
            ),
          ),
        ],
      ],
    );
  }
}

Future<String?> showLabelNameDialog(
  BuildContext context, {
  required String title,
  String initial = '',
  String submitLabel = 'Создать',
}) {
  return showDialog<String>(
    context: context,
    builder: (context) => _LabelNameDialog(
      title: title,
      initial: initial,
      submitLabel: submitLabel,
    ),
  );
}

class _LabelNameDialog extends StatefulWidget {
  const _LabelNameDialog({
    required this.title,
    required this.initial,
    required this.submitLabel,
  });

  final String title;
  final String initial;
  final String submitLabel;

  @override
  State<_LabelNameDialog> createState() => _LabelNameDialogState();
}

class _LabelNameDialogState extends State<_LabelNameDialog> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initial);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final trimmed = _controller.text.trim();
    return AlertDialog(
      title: Text(widget.title),
      content: TextField(
        controller: _controller,
        autofocus: true,
        decoration: const InputDecoration(labelText: 'Название'),
        onChanged: (_) => setState(() {}),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Отмена'),
        ),
        FilledButton(
          onPressed: trimmed.isEmpty ? null : () => Navigator.pop(context, trimmed),
          child: Text(widget.submitLabel),
        ),
      ],
    );
  }
}
