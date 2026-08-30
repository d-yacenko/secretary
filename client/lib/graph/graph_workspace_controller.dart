import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';
import 'graph_layout.dart';

enum GraphWorkspaceLoadState { idle, loading, ready, error }

class GraphWorkspaceController extends ChangeNotifier {
  GraphWorkspaceController({
    required SecretaryApiClient apiClient,
    required AuthController authController,
  })  : _apiClient = apiClient,
        _authController = authController;

  final SecretaryApiClient _apiClient;
  final AuthController _authController;

  GraphWorkspaceLoadState loadState = GraphWorkspaceLoadState.idle;
  String? errorMessage;
  String? rootId;
  bool truncated = false;
  String? selectedObjectId;
  String? selectedEdgeId;
  String? searchQuery;
  String? searchKindFilter;
  bool shouldFitAfterLayout = false;

  final Map<String, SecretaryObject> _nodes = {};
  final List<SecretaryEdge> _edges = [];
  final Map<String, Offset> _positions = {};

  List<SecretaryObject> get nodes => _nodes.values.toList();
  SecretaryObject? nodeById(String id) => _nodes[id];
  List<SecretaryEdge> get edges => List.unmodifiable(_edges);
  Map<String, Offset> get positions => Map.unmodifiable(_positions);

  SecretaryObject? get selectedObject =>
      selectedObjectId == null ? null : _nodes[selectedObjectId!];

  SecretaryEdge? get selectedEdge {
    if (selectedEdgeId == null) {
      return null;
    }
    for (final edge in _edges) {
      if (edge.id == selectedEdgeId) {
        return edge;
      }
    }
    return null;
  }

  void resetSession() {
    loadState = GraphWorkspaceLoadState.idle;
    errorMessage = null;
    rootId = null;
    truncated = false;
    selectedObjectId = null;
    selectedEdgeId = null;
    searchQuery = null;
    searchKindFilter = null;
    shouldFitAfterLayout = false;
    _nodes.clear();
    _edges.clear();
    _positions.clear();
    notifyListeners();
  }

  Future<void> loadOverview() async {
    loadState = GraphWorkspaceLoadState.loading;
    errorMessage = null;
    notifyListeners();
    try {
      final workspace = await _apiClient.getGraphWorkspace();
      _nodes.clear();
      _edges.clear();
      _positions.clear();
      _applyWorkspace(workspace, layoutRoot: null, freshRoot: true);
      rootId = null;
      selectedObjectId = null;
      loadState = GraphWorkspaceLoadState.ready;
      shouldFitAfterLayout = true;
    } on AuthenticationException {
      _authController.handleAuthenticationFailure();
    } on ApiException catch (error) {
      loadState = GraphWorkspaceLoadState.error;
      errorMessage = error.message;
    } catch (_) {
      loadState = GraphWorkspaceLoadState.error;
      errorMessage = 'Failed to load graph workspace';
    }
    notifyListeners();
  }

  Future<void> reRoot(String objectId) async {
    loadState = GraphWorkspaceLoadState.loading;
    errorMessage = null;
    notifyListeners();
    try {
      final workspace = await _apiClient.getGraphWorkspace(rootId: objectId);
      _nodes.clear();
      _edges.clear();
      _positions.clear();
      _applyWorkspace(workspace, layoutRoot: objectId, freshRoot: true);
      rootId = objectId;
      selectedObjectId = objectId;
      selectedEdgeId = null;
      loadState = GraphWorkspaceLoadState.ready;
      shouldFitAfterLayout = true;
    } on AuthenticationException {
      _authController.handleAuthenticationFailure();
    } on ApiException catch (error) {
      loadState = GraphWorkspaceLoadState.ready;
      errorMessage = error.message;
    } catch (_) {
      loadState = GraphWorkspaceLoadState.ready;
      errorMessage = 'Failed to load graph workspace';
    }
    notifyListeners();
  }

  Future<void> expandSelected() async {
    final selected = selectedObject;
    if (selected == null) {
      return;
    }
    try {
      final workspace = await _apiClient.getGraphWorkspace(rootId: selected.id);
      _mergeWorkspace(workspace, expandAround: selected.id);
      errorMessage = null;
    } on AuthenticationException {
      _authController.handleAuthenticationFailure();
    } on ApiException catch (error) {
      errorMessage = error.message;
      notifyListeners();
    } catch (_) {
      errorMessage = 'Failed to expand neighbors';
      notifyListeners();
    }
  }

  Future<void> mergeRelationContext(String sourceId, SecretaryObject? target) async {
    if (target != null) {
      _nodes[target.id] = target;
    }
    try {
      final workspace = await _apiClient.getGraphWorkspace(rootId: sourceId);
      _mergeWorkspace(workspace, expandAround: sourceId);
      errorMessage = null;
    } on AuthenticationException {
      _authController.handleAuthenticationFailure();
    } on ApiException catch (error) {
      errorMessage = error.message;
      notifyListeners();
    } catch (_) {
      errorMessage = 'Failed to refresh graph after relation change';
      notifyListeners();
    }
  }

  void selectObject(String? objectId) {
    selectedObjectId = objectId;
    selectedEdgeId = null;
    notifyListeners();
  }

  void selectEdge(String? edgeId) {
    selectedEdgeId = edgeId;
    notifyListeners();
  }

  void upsertObject(SecretaryObject object) {
    _nodes[object.id] = object;
    notifyListeners();
  }

  void removeEdge(String edgeId) {
    _edges.removeWhere((edge) => edge.id == edgeId);
    if (selectedEdgeId == edgeId) {
      selectedEdgeId = null;
    }
    notifyListeners();
  }

  void addEdge(SecretaryEdge edge) {
    final exists = _edges.any((item) => item.id == edge.id);
    if (!exists) {
      _edges.add(edge);
    }
    notifyListeners();
  }

  void clearFitRequest() {
    shouldFitAfterLayout = false;
  }

  void _mergeWorkspace(GraphWorkspaceOut workspace, {required String expandAround}) {
    truncated = workspace.truncated;
    for (final node in workspace.nodes) {
      _nodes[node.id] = node;
    }
    for (final edge in workspace.edges) {
      final exists = _edges.any((item) => item.id == edge.id);
      if (!exists) {
        _edges.add(edge);
      }
    }
    final computed = GraphLayout.computePositions(
      nodes: workspace.nodes,
      rootId: expandAround,
      existing: _positions,
      freshRoot: false,
    );
    _positions.addAll(computed);
    loadState = GraphWorkspaceLoadState.ready;
    notifyListeners();
  }

  void _applyWorkspace(
    GraphWorkspaceOut workspace, {
    required String? layoutRoot,
    required bool freshRoot,
  }) {
    truncated = workspace.truncated;
    for (final node in workspace.nodes) {
      _nodes[node.id] = node;
    }
    for (final edge in workspace.edges) {
      final exists = _edges.any((item) => item.id == edge.id);
      if (!exists) {
        _edges.add(edge);
      }
    }
    final computed = GraphLayout.computePositions(
      nodes: workspace.nodes,
      rootId: layoutRoot,
      existing: _positions,
      freshRoot: freshRoot,
    );
    _positions.addAll(computed);
  }
}
