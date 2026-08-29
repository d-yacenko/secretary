import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../navigation/secretary_navigation.dart';

enum ObjectDetailLoadState { loading, ready, error }

class ObjectDetailScreen extends StatefulWidget {
  const ObjectDetailScreen({
    super.key,
    required this.objectId,
    required this.apiClient,
    required this.authController,
    required this.captureController,
  });

  final String objectId;
  final SecretaryApiClient apiClient;
  final AuthController authController;
  final CaptureController captureController;

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
    setState(() {
      _loadState = ObjectDetailLoadState.loading;
      _errorMessage = null;
    });

    try {
      final object = await widget.apiClient.getObject(widget.objectId);
      final neighbors = await widget.apiClient.getObjectNeighbors(widget.objectId);
      final context = await widget.apiClient.getObjectContext(widget.objectId);
      setState(() {
        _object = object;
        _neighbors = neighbors.neighbors;
        _context = context;
        _loadState = ObjectDetailLoadState.ready;
      });
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_object?.title ?? 'Object'),
        actions: [
          if (_object != null)
            TextButton(
              onPressed: _useAsTaskContext,
              child: const Text('Use as task context'),
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
              Text(_errorMessage ?? 'Failed to load object'),
              const SizedBox(height: 12),
              FilledButton(onPressed: _load, child: const Text('Retry')),
            ],
          ),
        );
      case ObjectDetailLoadState.ready:
        final object = _object!;
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _FieldRow(label: 'Kind', value: object.kind),
            if (object.status != null) _FieldRow(label: 'Status', value: object.status!),
            _FieldRow(label: 'State', value: object.state),
            _FieldRow(label: 'Origin', value: object.origin),
            if (object.body != null) _FieldRow(label: 'Body', value: object.body!),
            if (object.startAt != null)
              _FieldRow(label: 'Start', value: object.startAt!),
            if (object.dueAt != null) _FieldRow(label: 'Due', value: object.dueAt!),
            if (object.provider != null)
              _FieldRow(label: 'Provider', value: object.provider!),
            if (object.canonicalUri != null)
              _CanonicalUriRow(uri: object.canonicalUri!),
            const SizedBox(height: 16),
            Text('Relations', style: Theme.of(context).textTheme.titleMedium),
            if (_neighbors.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text('No relations'),
              )
            else
              ..._neighbors.map(
                (neighbor) => ListTile(
                  title: Text(neighbor.object.title),
                  subtitle: Text(
                    '${neighbor.edge.type} • ${neighbor.direction} • ${neighbor.object.kind}',
                  ),
                ),
              ),
            const SizedBox(height: 16),
            Text('Context', style: Theme.of(context).textTheme.titleMedium),
            if (_context == null || _context!.neighbors.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text('No context neighbors'),
              )
            else
              ..._context!.neighbors.map(
                (neighbor) => ListTile(
                  title: Text(neighbor.title),
                  subtitle: Text(neighbor.kind),
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
          Text('Canonical URI', style: Theme.of(context).textTheme.labelLarge),
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
