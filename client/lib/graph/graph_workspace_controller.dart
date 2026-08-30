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
    _nodes.clear();
    _edges.clear();
    _positions.clear();
    notifyListeners();
  }

  Future<void> loadOverview() async {
    await _loadWorkspace(rootId: null, clearPositions: true, clearGraph: true);
  }

  Future<void> loadRoot(String objectId, {bool clearPositions = false}) async {
    await _loadWorkspace(
      rootId: objectId,
      clearPositions: clearPositions,
      clearGraph: clearPositions,
    );
    selectedObjectId = objectId;
  }

  Future<void> expandSelected() async {
    final selected = selectedObject;
    if (selected == null) {
      return;
    }
    await _mergeWorkspace(
      await _apiClient.getGraphWorkspace(rootId: selected.id),
      expandAround: selected.id,
    );
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

  Future<void> _loadWorkspace({
    required String? rootId,
    required bool clearPositions,
    required bool clearGraph,
  }) async {
    loadState = GraphWorkspaceLoadState.loading;
    errorMessage = null;
    notifyListeners();
    try {
      final workspace = await _apiClient.getGraphWorkspace(rootId: rootId);
      if (clearPositions) {
        _positions.clear();
      }
      if (clearGraph) {
        _nodes.clear();
        _edges.clear();
      }
      _applyWorkspace(workspace, expandAround: rootId);
      loadState = GraphWorkspaceLoadState.ready;
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

  Future<void> _mergeWorkspace(
    GraphWorkspaceOut workspace, {
    String? expandAround,
  }) async {
    _applyWorkspace(workspace, expandAround: expandAround);
    loadState = GraphWorkspaceLoadState.ready;
    notifyListeners();
  }

  void _applyWorkspace(GraphWorkspaceOut workspace, {String? expandAround}) {
    rootId = workspace.rootId;
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
    final layoutRoot = expandAround ?? workspace.rootId;
    final computed = GraphLayout.computePositions(
      nodes: workspace.nodes,
      rootId: layoutRoot,
      existing: _positions,
    );
    _positions.addAll(computed);
  }
}
