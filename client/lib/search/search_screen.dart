import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../assistant/assistant_controller.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../navigation/secretary_navigation.dart';
import '../ui/compact_object_filters.dart';
import '../ui/domain_labels.dart';
import '../ui/object_dates.dart';
import '../ui/object_presentation.dart';

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
  String _selectedSort = 'relevance';
  SearchFacetsOut? _facets;

  @override
  void initState() {
    super.initState();
    _loadFacets();
  }

  Future<void> _loadFacets() async {
    try {
      final facets = await widget.apiClient.getSearchFacets();
      if (mounted) {
        setState(() => _facets = facets);
      }
    } catch (_) {}
  }

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
        sort: _selectedSort,
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

  Future<void> _openObject(SecretaryObject object) async {
    final result = await openObjectDetail(
      context,
      objectId: object.id,
      apiClient: widget.apiClient,
      authController: widget.authController,
      captureController: widget.captureController,
      assistantController: widget.assistantController,
      onAskSecretary: widget.onAskSecretary,
      onShowInGraph: widget.onShowInGraph,
    );
    if (!mounted || result == null) {
      return;
    }
    setState(() {
      _results =
          _results.where((row) => row.id != result.deletedObjectId).toList();
      if (_results.isEmpty && _loadState == SearchLoadState.ready) {
        _loadState = SearchLoadState.empty;
      }
    });
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
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _queryController,
                      decoration: const InputDecoration(
                        labelText: 'Поиск',
                        hintText: 'Найти задачи, письма, проекты…',
                        border: OutlineInputBorder(),
                      ),
                      textInputAction: TextInputAction.search,
                      onSubmitted: (_) => _search(),
                    ),
                  ),
                  CompactObjectFilters(
                    facets: _facets,
                    selectedKind: _selectedKind,
                    selectedProvider: _selectedProvider,
                    selectedSort: _selectedSort,
                    showSort: true,
                    onKindChanged: (value) {
                      setState(() => _selectedKind = value);
                      if (_queryController.text.trim().isNotEmpty) {
                        _search();
                      }
                    },
                    onProviderChanged: (value) {
                      setState(() => _selectedProvider = value);
                      if (_queryController.text.trim().isNotEmpty) {
                        _search();
                      }
                    },
                    onSortChanged: (value) {
                      setState(() => _selectedSort = value);
                      if (_queryController.text.trim().isNotEmpty) {
                        _search();
                      }
                    },
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton(
                  onPressed: _loadState == SearchLoadState.loading ? null : _search,
                  child: const Text('Поиск'),
                ),
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
    final dateLabel = objectPrimaryDateLabel(object);
    final statusLine = _statusLine(object, snippet);

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ObjectCompactHeaderRow(
                title: object.title,
                kind: object.kind,
                provider: object.provider,
                trailingText: dateLabel,
              ),
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
      ),
    );
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
