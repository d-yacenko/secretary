import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';
import '../assistant/assistant_controller.dart';
import '../capture/capture_controller.dart';
import '../navigation/secretary_navigation.dart';
import '../navigation/source_navigation_service.dart';
import '../tasks/task_management_actions.dart';
import '../ui/date_format.dart';
import '../ui/domain_labels.dart';
import '../ui/object_dates.dart';
import '../ui/object_visuals.dart';

enum ObjectDetailLoadState { loading, ready, error }

class ObjectDetailScreen extends StatefulWidget {
  const ObjectDetailScreen({
    super.key,
    required this.objectId,
    required this.apiClient,
    required this.authController,
    required this.captureController,
    this.assistantController,
    this.onAskSecretary,
    this.onShowInGraph,
    this.onTaskUpdated,
  });

  final String objectId;
  final SecretaryApiClient apiClient;
  final AuthController authController;
  final CaptureController captureController;
  final AssistantController? assistantController;
  final AskSecretaryHandler? onAskSecretary;
  final ShowInGraphHandler? onShowInGraph;
  final ValueChanged<SecretaryObject>? onTaskUpdated;

  @override
  State<ObjectDetailScreen> createState() => _ObjectDetailScreenState();
}

class _ObjectDetailScreenState extends State<ObjectDetailScreen> {
  ObjectDetailLoadState _loadState = ObjectDetailLoadState.loading;
  SecretaryObject? _object;
  List<NeighborOut> _neighbors = [];
  ContextResponse? _context;
  OpenTarget? _openTarget;
  String? _errorMessage;
  late final SourceNavigationService _sourceNavigation;

  @override
  void initState() {
    super.initState();
    _sourceNavigation = SourceNavigationService(apiClient: widget.apiClient);
    _load();
  }

  Future<void> _load() async {
    if (!mounted) {
      return;
    }
    setState(() {
      _loadState = ObjectDetailLoadState.loading;
      _errorMessage = null;
    });

    try {
      final object = await widget.apiClient.getObject(widget.objectId);
      if (!mounted) {
        return;
      }
      final neighbors = await widget.apiClient.getObjectNeighbors(widget.objectId);
      if (!mounted) {
        return;
      }
      final context = await widget.apiClient.getObjectContext(widget.objectId);
      if (!mounted) {
        return;
      }
      OpenTarget? openTarget;
      try {
        openTarget = await widget.apiClient.getOpenTarget(widget.objectId);
      } on ApiException {
        openTarget = null;
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _object = object;
        _neighbors = neighbors.neighbors;
        _context = context;
        _openTarget = openTarget;
        _loadState = ObjectDetailLoadState.ready;
      });
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loadState = ObjectDetailLoadState.error;
        _errorMessage = e.message;
      });
    }
  }

  void _useAsTaskContext() {
    final object = _object;
    if (object == null) {
      return;
    }
    widget.captureController.attachObjectContext(object);
    openCapture(context, captureController: widget.captureController);
  }

  void _askSecretary() {
    final object = _object;
    if (object == null || widget.onAskSecretary == null) {
      return;
    }
    widget.onAskSecretary!(object);
    Navigator.of(context).pop();
  }

  void _notifyTaskUpdated(SecretaryObject updated) {
    setState(() => _object = updated);
    widget.onTaskUpdated?.call(updated);
  }

  Future<void> _deleteTask() async {
    final object = _object;
    if (object == null) {
      return;
    }
    await confirmAndDeleteTask(
      context,
      task: object,
      apiClient: widget.apiClient,
      authController: widget.authController,
      onTaskUpdated: _notifyTaskUpdated,
    );
  }

  Future<void> _openSource() async {
    try {
      await _sourceNavigation.launchForObject(widget.objectId);
    } on SourceLaunchException catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  List<NeighborOut> get _attachmentNeighbors {
    return _neighbors.where(
      (neighbor) =>
          neighbor.edge.type == 'contains' &&
          neighbor.direction == 'outgoing' &&
          neighbor.object.kind == 'file',
    ).toList();
  }

  bool get _showDeleteAction {
    final object = _object;
    return object != null && object.kind == 'task' && !object.isDeletedTask;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_object?.title ?? 'Объект'),
        actions: [
          if (_showDeleteAction)
            IconButton(
              key: const Key('object_detail_delete'),
              tooltip: 'Удалить задачу',
              icon: const Icon(Icons.delete_outline),
              onPressed: _deleteTask,
            ),
          if (_object != null && widget.onShowInGraph != null)
            TextButton(
              onPressed: () {
                widget.onShowInGraph!(_object!.id);
                Navigator.of(context).pop();
              },
              child: const Text('Показать в графе'),
            ),
          if (_object != null && widget.onAskSecretary != null)
            TextButton(
              onPressed: _askSecretary,
              child: const Text('Спросить секретаря'),
            ),
          if (_object != null)
            TextButton(
              onPressed: _useAsTaskContext,
              child: const Text('Использовать как контекст задачи'),
            ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    switch (_loadState) {
      case ObjectDetailLoadState.loading:
        return const Center(child: CircularProgressIndicator());
      case ObjectDetailLoadState.error:
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_errorMessage ?? 'Не удалось загрузить объект'),
              const SizedBox(height: 12),
              FilledButton(onPressed: _load, child: const Text('Повторить')),
            ],
          ),
        );
      case ObjectDetailLoadState.ready:
        final object = _object!;
        final primaryDateValue = objectPrimaryDateDisplayValue(object);
        return SelectionArea(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (_openTarget != null && _openTarget!.available)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: FilledButton(
                    key: const Key('object_detail_open_source'),
                    onPressed: _openSource,
                    child: Text(_openTarget!.label),
                  ),
                ),
              if (primaryDateValue.isNotEmpty)
                _FieldRow(
                  label: objectPrimaryDateFieldLabel(object),
                  value: primaryDateValue,
                ),
              _FieldRow(label: 'Тип', value: objectKindLabel(object.kind)),
              if (object.status != null)
                _FieldRow(label: 'Статус', value: taskStatusLabel(object.status)),
              _FieldRow(label: 'Состояние', value: provenanceStateLabel(object.state)),
              _FieldRow(label: 'Источник', value: originLabel(object.origin)),
              _FieldRow(
                label: 'Создано',
                value: formatUserDateTime(object.createdAt),
              ),
              _FieldRow(
                label: 'Обновлено',
                value: formatUserDateTime(object.updatedAt),
              ),
              if (object.body != null) _FieldRow(label: 'Текст', value: object.body!),
              if (_attachmentNeighbors.isNotEmpty) ...[
                const SizedBox(height: 16),
                Text('Вложения', style: Theme.of(context).textTheme.titleMedium),
                ..._attachmentNeighbors.map(
                  (neighbor) => ListTile(
                    leading: const Icon(Icons.attach_file),
                    title: Text(neighbor.object.title),
                    subtitle: Text(
                      neighbor.object.metadata['mime_type']?.toString() ??
                          neighbor.object.metadata['size']?.toString() ??
                          objectKindLabel(neighbor.object.kind),
                    ),
                    onTap: () => openObjectDetail(
                      context,
                      objectId: neighbor.object.id,
                      apiClient: widget.apiClient,
                      authController: widget.authController,
                      captureController: widget.captureController,
                      assistantController: widget.assistantController,
                      onAskSecretary: widget.onAskSecretary,
                      onShowInGraph: widget.onShowInGraph,
                      onTaskUpdated: widget.onTaskUpdated,
                    ),
                  ),
                ),
              ],
              if (object.provider != null)
                _FieldRow(label: 'Провайдер', value: providerLabel(object.provider!)),
              if (object.canonicalUri != null)
                _CanonicalUriRow(uri: object.canonicalUri!),
              if (object.metadata.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text('Метаданные', style: Theme.of(context).textTheme.labelLarge),
                const SizedBox(height: 4),
                Text(_formatMetadata(object.metadata)),
              ],
              const SizedBox(height: 16),
              Text('Связи', style: Theme.of(context).textTheme.titleMedium),
              if (_neighbors.isEmpty)
                const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: Text('Нет связей'),
                )
              else
                ..._neighbors.map(
                  (neighbor) => ListTile(
                    title: Text(neighbor.object.title),
                    subtitle: Text(
                      '${relationTypeLabel(neighbor.edge.type)} • '
                      '${neighborDirectionLabel(neighbor.direction)} • '
                      '${objectKindLabel(neighbor.object.kind)}',
                    ),
                    onTap: () => openObjectDetail(
                      context,
                      objectId: neighbor.object.id,
                      apiClient: widget.apiClient,
                      authController: widget.authController,
                      captureController: widget.captureController,
                      assistantController: widget.assistantController,
                      onAskSecretary: widget.onAskSecretary,
                      onShowInGraph: widget.onShowInGraph,
                      onTaskUpdated: widget.onTaskUpdated,
                    ),
                  ),
                ),
              const SizedBox(height: 16),
              if (_object != null)
                TaskManagementActions(
                  task: _object!,
                  apiClient: widget.apiClient,
                  authController: widget.authController,
                  onTaskUpdated: _notifyTaskUpdated,
                ),
              const SizedBox(height: 16),
              Text('Контекст', style: Theme.of(context).textTheme.titleMedium),
              if (_context == null || _context!.neighbors.isEmpty)
                const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: Text('Нет соседнего контекста'),
                )
              else
                ..._context!.neighbors.map(
                  (neighbor) => ListTile(
                    title: Text(neighbor.title),
                    subtitle: Text(objectKindLabel(neighbor.kind)),
                  ),
                ),
            ],
          ),
        );
    }
  }

  String _formatMetadata(Map<String, dynamic> metadata) {
    const encoder = JsonEncoder.withIndent('  ');
    return encoder.convert(metadata);
  }
}

class _FieldRow extends StatelessWidget {
  const _FieldRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.labelLarge),
          Text(value),
        ],
      ),
    );
  }
}

class _CanonicalUriRow extends StatelessWidget {
  const _CanonicalUriRow({required this.uri});

  final String uri;

  @override
  Widget build(BuildContext context) {
    final sanitized = _stripCredentials(uri);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Канонический URI', style: Theme.of(context).textTheme.labelLarge),
          SelectableText(
            sanitized,
            onTap: () => Clipboard.setData(ClipboardData(text: sanitized)),
          ),
        ],
      ),
    );
  }

  String _stripCredentials(String value) {
    final parsed = Uri.tryParse(value);
    if (parsed == null) {
      return value;
    }
    if (parsed.userInfo.isEmpty) {
      return value;
    }
    return parsed.replace(userInfo: '').toString();
  }
}
