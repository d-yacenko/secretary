import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';
import '../assistant/assistant_controller.dart';
import '../capture/capture_controller.dart';
import '../navigation/secretary_navigation.dart';
import '../tasks/task_management_actions.dart';
import '../ui/date_format.dart';
import '../ui/domain_labels.dart';

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
  });

  final String objectId;
  final SecretaryApiClient apiClient;
  final AuthController authController;
  final CaptureController captureController;
  final AssistantController? assistantController;
  final AskSecretaryHandler? onAskSecretary;
  final ShowInGraphHandler? onShowInGraph;

  @override
  State<ObjectDetailScreen> createState() => _ObjectDetailScreenState();
}

class _ObjectDetailScreenState extends State<ObjectDetailScreen> {
  ObjectDetailLoadState _loadState = ObjectDetailLoadState.loading;
  SecretaryObject? _object;
  List<NeighborOut> _neighbors = [];
  ContextResponse? _context;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
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
      setState(() {
        _object = object;
        _neighbors = neighbors.neighbors;
        _context = context;
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_object?.title ?? 'Объект'),
        actions: [
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
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _FieldRow(label: 'Тип', value: objectKindLabel(object.kind)),
            if (object.status != null)
              _FieldRow(label: 'Статус', value: taskStatusLabel(object.status)),
            _FieldRow(label: 'Состояние', value: provenanceStateLabel(object.state)),
            _FieldRow(label: 'Источник', value: originLabel(object.origin)),
            if (object.body != null) _FieldRow(label: 'Текст', value: object.body!),
            if (object.startAt != null)
              _FieldRow(label: 'Начало', value: formatUserDateTime(object.startAt)),
            if (object.dueAt != null)
              _FieldRow(label: 'Срок', value: formatUserDateTime(object.dueAt)),
            if (object.provider != null)
              _FieldRow(label: 'Провайдер', value: object.provider!),
            if (object.canonicalUri != null)
              _CanonicalUriRow(uri: object.canonicalUri!),
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
                  ),
                ),
              ),
            const SizedBox(height: 16),
            if (_object != null)
              TaskManagementActions(
                task: _object!,
                apiClient: widget.apiClient,
                authController: widget.authController,
                onTaskUpdated: (updated) => setState(() => _object = updated),
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
        );
    }
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
