import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../assistant/assistant_controller.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../navigation/secretary_navigation.dart';
import '../ui/domain_labels.dart';
import '../ui/object_dates.dart';
import '../ui/object_visuals.dart';

enum SearchLoadState { idle, loading, ready, empty, error }

class SearchScreen extends StatefulWidget {
  const SearchScreen({
    super.key,
    required this.apiClient,
    required this.authController,
    required this.captureController,
    this.assistantController,
    this.onAskSecretary,
    this.onShowInGraph,
  });

  final SecretaryApiClient apiClient;
  final AuthController authController;
  final CaptureController captureController;
  final AssistantController? assistantController;
  final AskSecretaryHandler? onAskSecretary;
  final ShowInGraphHandler? onShowInGraph;

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final _queryController = TextEditingController();
  SearchLoadState _loadState = SearchLoadState.idle;
  List<SecretaryObject> _results = [];
  String? _errorMessage;
  String? _selectedKind;
  String? _selectedProvider;

  static const _kindOptions = <String?>[null, 'task', 'project', 'email', 'event', 'note'];

  static const _providerOptions = <(String?, String)>[
    (null, 'Все источники'),
    ('gmail', 'Gmail'),
    ('yandex_mail', 'Яндекс'),
    ('local_device', 'Компьютер'),
  ];

  @override
  void dispose() {
    _queryController.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final query = _queryController.text.trim();
    if (query.isEmpty) {
      return;
    }
    if (!mounted) {
      return;
    }
    setState(() {
      _loadState = SearchLoadState.loading;
      _errorMessage = null;
    });

    try {
      final results = await widget.apiClient.searchObjects(
        query: query,
        kind: _selectedKind,
        provider: _selectedProvider,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _results = results;
        _loadState = results.isEmpty ? SearchLoadState.empty : SearchLoadState.ready;
      });
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loadState = SearchLoadState.error;
        _errorMessage = e.message;
      });
    }
  }

  void _openObject(SecretaryObject object) {
    openObjectDetail(
      context,
      objectId: object.id,
      apiClient: widget.apiClient,
      authController: widget.authController,
      captureController: widget.captureController,
      assistantController: widget.assistantController,
      onAskSecretary: widget.onAskSecretary,
      onShowInGraph: widget.onShowInGraph,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextField(
                controller: _queryController,
                decoration: const InputDecoration(
                  labelText: 'Поиск',
                  hintText: 'Найти задачи, письма, проекты…',
                  border: OutlineInputBorder(),
                ),
                textInputAction: TextInputAction.search,
                onSubmitted: (_) => _search(),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: DropdownButtonFormField<String?>(
                      initialValue: _selectedKind,
                      decoration: const InputDecoration(
                        labelText: 'Тип',
                        border: OutlineInputBorder(),
                      ),
                      items: _kindOptions
                          .map(
                            (kind) => DropdownMenuItem<String?>(
                              value: kind,
                              child: Text(searchKindFilterLabel(kind)),
                            ),
                          )
                          .toList(),
                      onChanged: (value) => setState(() => _selectedKind = value),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: DropdownButtonFormField<String?>(
                      initialValue: _selectedProvider,
                      decoration: const InputDecoration(
                        labelText: 'Источник',
                        border: OutlineInputBorder(),
                      ),
                      items: _providerOptions
                          .map(
                            (option) => DropdownMenuItem<String?>(
                              value: option.$1,
                              child: Text(option.$2),
                            ),
                          )
                          .toList(),
                      onChanged: (value) => setState(() => _selectedProvider = value),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Text(
                    'По релевантности',
                    style: Theme.of(context).textTheme.labelMedium,
                  ),
                  const Spacer(),
                  FilledButton(
                    onPressed: _loadState == SearchLoadState.loading ? null : _search,
                    child: const Text('Поиск'),
                  ),
                ],
              ),
            ],
          ),
        ),
        Expanded(child: _buildBody()),
      ],
    );
  }

  Widget _buildBody() {
    switch (_loadState) {
      case SearchLoadState.idle:
        return const Center(child: Text('Введите запрос и нажмите «Поиск»'));
      case SearchLoadState.loading:
        return const Center(child: CircularProgressIndicator());
      case SearchLoadState.empty:
        return const Center(child: Text('Ничего не найдено'));
      case SearchLoadState.error:
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_errorMessage ?? 'Ошибка поиска'),
              const SizedBox(height: 12),
              FilledButton(onPressed: _search, child: const Text('Повторить')),
            ],
          ),
        );
      case SearchLoadState.ready:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              child: Text(
                'Показано: ${_results.length}',
                style: Theme.of(context).textTheme.labelMedium,
              ),
            ),
            Expanded(
              child: ListView.separated(
                itemCount: _results.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (context, index) {
                  final object = _results[index];
                  return _SearchResultTile(
                    object: object,
                    onTap: () => _openObject(object),
                  );
                },
              ),
            ),
          ],
        );
    }
  }
}

class _SearchResultTile extends StatelessWidget {
  const _SearchResultTile({
    required this.object,
    required this.onTap,
  });

  final SecretaryObject object;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final snippet = SearchResultSnippet.fromBody(object.body);
    final typeSource = _typeSourceLine(object);
    final dateLabel = objectPrimaryDateLabel(object);
    final statusLine = _statusLine(object, snippet);

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Icon(
                  iconForKind(object.kind),
                  size: 22,
                  color: theme.colorScheme.primary,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      object.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (typeSource.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        typeSource,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                    if (dateLabel.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(
                        dateLabel,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                    if (statusLine.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        statusLine,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodySmall,
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _typeSourceLine(SecretaryObject object) {
    final kind = objectKindLabel(object.kind);
    final provider = providerLabel(object.provider);
    if (provider.isNotEmpty) {
      return '$kind · $provider';
    }
    return kind;
  }

  String _statusLine(SecretaryObject object, String snippet) {
    if (object.kind == 'task' && object.status != null) {
      return taskStatusLabel(object.status);
    }
    if (snippet.isNotEmpty) {
      return snippet;
    }
    if (object.state.isNotEmpty) {
      return provenanceStateLabel(object.state);
    }
    return '';
  }
}
