import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/auth/token_store.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';
import 'package:personal_secretary/graph/graph_workspace_controller.dart';

class _FakeApiClient extends SecretaryApiClient {
  _FakeApiClient(this._handler);

  final Future<GraphWorkspaceOut> Function(String? rootId) _handler;

  @override
  Future<GraphWorkspaceOut> getGraphWorkspace({
    String? rootId,
    int? seedLimit,
    int? neighborLimit,
    int? nodeLimit,
  }) {
    return _handler(rootId);
  }
}

class _FakeAuth extends AuthController {
  _FakeAuth()
      : super(
          apiClient: SecretaryApiClient(),
          tokenStore: FakeTokenStore(),
          serverUrlStore: FakeServerUrlStore(),
        );

  bool failed = false;

  @override
  void handleAuthenticationFailure() {
    failed = true;
  }
}

SecretaryObject _obj(String id, String title) {
  return SecretaryObject(
    id: id,
    kind: 'task',
    title: title,
    metadata: {},
    origin: 'user',
    state: 'confirmed',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
  );
}

GraphWorkspaceOut _workspace({
  String? rootId,
  List<SecretaryObject> nodes = const [],
}) {
  return GraphWorkspaceOut(
    rootId: rootId,
    seedIds: [],
    nodes: nodes,
    edges: [],
    truncated: false,
  );
}

void main() {
  test('reRoot replaces unrelated nodes and selects root', () async {
    final auth = _FakeAuth();
    final controller = GraphWorkspaceController(
      apiClient: _FakeApiClient((rootId) async {
        if (rootId == 'new-root') {
          return _workspace(rootId: 'new-root', nodes: [_obj('new-root', 'New')]);
        }
        return _workspace(nodes: [_obj('old', 'Old')]);
      }),
      authController: auth,
    );

    await controller.loadOverview();
    expect(controller.nodes.length, 1);
    expect(controller.nodes.first.id, 'old');

    await controller.reRoot('new-root');
    expect(controller.rootId, 'new-root');
    expect(controller.selectedObjectId, 'new-root');
    expect(controller.selectedObject, isNotNull);
    expect(controller.nodes.length, 1);
    expect(controller.nodes.first.id, 'new-root');
    expect(controller.positions.containsKey('new-root'), isTrue);
  });

  test('expandSelected preserves graph on error', () async {
    final auth = _FakeAuth();
    var calls = 0;
    final controller = GraphWorkspaceController(
      apiClient: _FakeApiClient((rootId) async {
        calls += 1;
        if (calls > 1) {
          throw Exception('network');
        }
        return _workspace(rootId: 'root', nodes: [_obj('root', 'Root')]);
      }),
      authController: auth,
    );

    await controller.reRoot('root');
    await controller.expandSelected();
    expect(controller.nodes.length, 1);
    expect(controller.errorMessage, isNotNull);
  });

  test('expand merges neighbors without duplicate nodes', () async {
    final auth = _FakeAuth();
    final controller = GraphWorkspaceController(
      apiClient: _FakeApiClient((rootId) async {
        if (rootId == 'root') {
          return GraphWorkspaceOut(
            rootId: 'root',
            seedIds: ['root'],
            nodes: [_obj('root', 'Root'), _obj('n1', 'Neighbor')],
            edges: [
              SecretaryEdge(
                id: 'e1',
                sourceId: 'root',
                targetId: 'n1',
                type: 'references',
                origin: 'user',
                state: 'confirmed',
                metadata: {},
                createdAt: '2026-01-01T00:00:00Z',
                updatedAt: '2026-01-01T00:00:00Z',
              ),
            ],
            truncated: false,
          );
        }
        return _workspace(nodes: [_obj('root', 'Root')]);
      }),
      authController: auth,
    );

    await controller.reRoot('root');
    final rootPos = controller.positions['root'];
    await controller.expandSelected();

    expect(controller.nodes.length, 2);
    expect(controller.edges.length, 1);
    expect(controller.positions['root'], rootPos);
    expect(controller.positions.containsKey('n1'), isTrue);
  });

  test('mergeRelationContext positions absent target', () async {
    final auth = _FakeAuth();
    final controller = GraphWorkspaceController(
      apiClient: _FakeApiClient((rootId) async {
        return GraphWorkspaceOut(
          rootId: 'source',
          seedIds: ['source'],
          nodes: [_obj('source', 'Source'), _obj('target', 'Target')],
          edges: [
            SecretaryEdge(
              id: 'e1',
              sourceId: 'source',
              targetId: 'target',
              type: 'related_to',
              origin: 'user',
              state: 'confirmed',
              metadata: {},
              createdAt: '2026-01-01T00:00:00Z',
              updatedAt: '2026-01-01T00:00:00Z',
            ),
          ],
          truncated: false,
        );
      }),
      authController: auth,
    );

    await controller.reRoot('source');
    controller.removeEdge('e1');
    expect(controller.edges, isEmpty);

    await controller.mergeRelationContext(
      'source',
      _obj('target', 'Target'),
    );

    expect(controller.edges.length, 1);
    expect(controller.positions.containsKey('source'), isTrue);
    expect(controller.positions.containsKey('target'), isTrue);
  });

  test('selectObject updates selection', () {
    final auth = _FakeAuth();
    final controller = GraphWorkspaceController(
      apiClient: _FakeApiClient((_) async => _workspace()),
      authController: auth,
    );
    controller.upsertObject(_obj('a', 'A'));
    controller.selectObject('a');
    expect(controller.selectedObjectId, 'a');
    expect(controller.selectedObject?.title, 'A');
  });
}
