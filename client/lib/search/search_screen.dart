import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../assistant/assistant_controller.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../navigation/secretary_navigation.dart';

enum SearchLoadState { idle, loading, ready, empty, error }

class SearchScreen extends StatefulWidget {
  const SearchScreen({
    super.key,
    required this.apiClient,
    required this.authController,
    required this.captureController,
    this.assistantController,
    this.onAskSecretary,
  });

  final SecretaryApiClient apiClient;
  final AuthController authController;
  final CaptureController captureController;
  final AssistantController? assistantController;
  final AskSecretaryHandler? onAskSecretary;

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final _queryController = TextEditingController();
  SearchLoadState _loadState = SearchLoadState.idle;
  List<SecretaryObject> _results = [];
  String? _errorMessage;
  String? _selectedKind;

  static const _kindOptions = <String?>[null, 'task', 'project', 'email', 'event', 'note'];

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
                  labelText: 'Search',
                  hintText: 'Find tasks, emails, projects…',
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
                        labelText: 'Kind',
                        border: OutlineInputBorder(),
                      ),
                      items: _kindOptions
                          .map(
                            (kind) => DropdownMenuItem<String?>(
                              value: kind,
                              child: Text(kind ?? 'All kinds'),
                            ),
                          )
                          .toList(),
                      onChanged: (value) => setState(() => _selectedKind = value),
                    ),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                    onPressed: _loadState == SearchLoadState.loading ? null : _search,
                    child: const Text('Search'),
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
        return const Center(child: Text('Enter a query and press Search'));
      case SearchLoadState.loading:
        return const Center(child: CircularProgressIndicator());
      case SearchLoadState.empty:
        return const Center(child: Text('No results'));
      case SearchLoadState.error:
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_errorMessage ?? 'Search failed'),
              const SizedBox(height: 12),
              FilledButton(onPressed: _search, child: const Text('Retry')),
            ],
          ),
        );
      case SearchLoadState.ready:
        return ListView.separated(
          itemCount: _results.length,
          separatorBuilder: (_, __) => const Divider(height: 1),
          itemBuilder: (context, index) {
            final object = _results[index];
            final snippet = SearchResultSnippet.fromBody(object.body);
            return ListTile(
              title: Text(object.title),
              subtitle: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${object.kind}${object.provider != null ? ' • ${object.provider}' : ''}',
                  ),
                  if (object.status != null) Text('Status: ${object.status}'),
                  if (object.state.isNotEmpty) Text('State: ${object.state}'),
                  if (snippet.isNotEmpty) Text(snippet),
                ],
              ),
              onTap: () => _openObject(object),
            );
          },
        );
    }
  }
}
