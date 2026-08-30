import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/auth/token_store.dart';
import 'package:personal_secretary/assistant/assistant_controller.dart';
import 'package:personal_secretary/assistant/fake_voice_recorder.dart';
import 'package:personal_secretary/assistant/voice_temp_files.dart';
import 'package:personal_secretary/capture/capture_controller.dart';
import 'package:personal_secretary/graph/graph_layout.dart';
import 'package:personal_secretary/graph/graph_workspace_controller.dart';
import 'package:personal_secretary/graph/graph_workspace_screen.dart';
import 'package:personal_secretary/shell/app_shell.dart';

Map<String, dynamic> _objectJson({
  required String id,
  required String title,
  String kind = 'task',
  String status = 'open',
}) {
  return {
    'id': id,
    'kind': kind,
    'title': title,
    'body': null,
    'provider': null,
    'external_id': null,
    'canonical_uri': null,
    'status': status,
    'start_at': null,
    'due_at': null,
    'metadata': {},
    'origin': 'user',
    'state': 'confirmed',
    'confidence': null,
    'created_at': '2026-01-01T00:00:00Z',
    'updated_at': '2026-01-01T00:00:00Z',
  };
}

Map<String, dynamic> _workspaceJson({
  String? rootId,
  required List<Map<String, dynamic>> nodes,
  List<Map<String, dynamic>> edges = const [],
  bool truncated = false,
}) {
  return {
    'root_id': rootId,
    'seed_ids': nodes.map((n) => n['id']).toList(),
    'nodes': nodes,
    'edges': edges,
    'truncated': truncated,
  };
}

class GraphTestHarness {
  GraphTestHarness(this.mock);

  final MockClient mock;
  late final AuthController auth;
  late final CaptureController capture;
  late final AssistantController assistant;
  late final GraphWorkspaceController graph;

  void configure() {
    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: 'https://example.com', token: 'token');
    auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    auth.user = UserMe(
      id: 'u1',
      displayName: 'Alice',
      createdAt: '2026-01-01T00:00:00Z',
    );
    capture = CaptureController(apiClient: apiClient, authController: auth);
    assistant = AssistantController(
      apiClient: apiClient,
      authController: auth,
      voiceRecorder: FakeVoiceRecorder(),
      voiceTempFiles: VoiceTempFiles(
        directory: Directory.systemTemp.createTempSync('graph_screen_test'),
      ),
    );
    graph = GraphWorkspaceController(
      apiClient: apiClient,
      authController: auth,
    );
  }

  Widget app() {
    return MaterialApp(
      home: AppShell(
        authController: auth,
        captureController: capture,
        assistantController: assistant,
        graphController: graph,
      ),
    );
  }
}

MockClient overviewMock({
  bool truncated = true,
  String nodeId = 'task-1',
  String title = 'Graph task',
}) {
  return MockClient((request) async {
    if (request.url.path == '/notifications') {
      return http.Response(jsonEncode({'notifications': []}), 200);
    }
    if (request.url.path == '/today') {
      return http.Response(
        jsonEncode({
          'date': '2026-08-28',
          'timezone': 'Europe/Amsterdam',
          'day_start': '2026-08-28T00:00:00+02:00',
          'tasks': [],
          'calendar_events': [],
          'notifications': [],
        }),
        200,
      );
    }
    if (request.url.path == '/graph/workspace') {
      return http.Response(
        jsonEncode(
          _workspaceJson(
            nodes: [_objectJson(id: nodeId, title: title)],
            truncated: truncated,
          ),
        ),
        200,
      );
    }
    if (request.url.path == '/search') {
      return http.Response(
        jsonEncode([
          _objectJson(id: 'search-root', title: 'Search hit'),
        ]),
        200,
      );
    }
    return http.Response('{}', 404);
  });
}

Future<void> openGraph(WidgetTester tester, GraphTestHarness harness) async {
  await tester.pumpWidget(harness.app());
  await tester.pumpAndSettle();
  await tester.tap(find.text('Graph'));
  await tester.pumpAndSettle();
}

void main() {
  final sizes = <Size>[
    const Size(320, 640),
    const Size(360, 800),
    const Size(393, 852),
    const Size(1280, 800),
  ];

  for (final size in sizes) {
    testWidgets('graph screen smoke at ${size.width}x${size.height}', (tester) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final harness = GraphTestHarness(overviewMock());
      harness.configure();
      await openGraph(tester, harness);

      expect(find.byType(GraphWorkspaceScreen), findsOneWidget);
      expect(find.text('Graph task'), findsOneWidget);
      expect(find.byTooltip('Fit graph'), findsOneWidget);
      expect(find.byType(TextField), findsOneWidget);

      harness.graph.selectObject('task-1');
      await tester.pump();

      expect(harness.graph.selectedObjectId, 'task-1');
      expect(find.text('Ask Secretary'), findsOneWidget);
      expect(find.text('Expand'), findsOneWidget);

      if (size.width < 900) {
        expect(find.byType(FloatingActionButton), findsNothing);
        expect(find.byTooltip('Capture'), findsOneWidget);
      }

      await tester.tap(find.byTooltip('Fit graph'));
      await tester.pumpAndSettle();
    });
  }

  testWidgets('search result performs true re-root', (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final harness = GraphTestHarness(
      MockClient((request) async {
        if (request.url.path == '/notifications') {
          return http.Response(jsonEncode({'notifications': []}), 200);
        }
        if (request.url.path == '/today') {
          return http.Response(
            jsonEncode({
              'date': '2026-08-28',
              'timezone': 'Europe/Amsterdam',
              'day_start': '2026-08-28T00:00:00+02:00',
              'tasks': [],
              'calendar_events': [],
              'notifications': [],
            }),
            200,
          );
        }
        if (request.url.path == '/graph/workspace') {
          final root = request.url.queryParameters['root_id'];
          if (root == 'search-root') {
            return http.Response(
              jsonEncode(
                _workspaceJson(
                  rootId: 'search-root',
                  nodes: [_objectJson(id: 'search-root', title: 'Search hit')],
                ),
              ),
              200,
            );
          }
          return http.Response(
            jsonEncode(
              _workspaceJson(
                nodes: [_objectJson(id: 'old-node', title: 'Old node')],
              ),
            ),
            200,
          );
        }
        if (request.url.path == '/search') {
          return http.Response(
            jsonEncode([
              _objectJson(id: 'search-root', title: 'Search hit'),
            ]),
            200,
          );
        }
        return http.Response('{}', 404);
      }),
    );
    harness.configure();
    await openGraph(tester, harness);

    expect(find.text('Old node'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'hit');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();

    await tester.tap(find.text('Search hit'));
    await tester.pumpAndSettle();

    expect(harness.graph.rootId, 'search-root');
    expect(harness.graph.selectedObjectId, 'search-root');
    expect(find.text('Old node'), findsNothing);
    expect(find.text('Search hit'), findsWidgets);
  });

  testWidgets('truncated indicator visible', (tester) async {
    tester.view.physicalSize = const Size(1280, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final harness = GraphTestHarness(overviewMock(truncated: true));
    harness.configure();
    await openGraph(tester, harness);

    expect(
      find.text('Some connected objects are hidden by the workspace limit.'),
      findsOneWidget,
    );
  });

  testWidgets('large canvas stays unconstrained and distant node reachable after fit at 320x640',
      (tester) async {
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final nodes = List.generate(
      12,
      (index) => _objectJson(id: 'wide-$index', title: 'Wide graph $index'),
    );
    final harness = GraphTestHarness(
      MockClient((request) async {
        if (request.url.path == '/notifications') {
          return http.Response(jsonEncode({'notifications': []}), 200);
        }
        if (request.url.path == '/today') {
          return http.Response(
            jsonEncode({
              'date': '2026-08-28',
              'timezone': 'Europe/Amsterdam',
              'day_start': '2026-08-28T00:00:00+02:00',
              'tasks': [],
              'calendar_events': [],
              'notifications': [],
            }),
            200,
          );
        }
        if (request.url.path == '/graph/workspace') {
          return http.Response(
            jsonEncode(_workspaceJson(nodes: nodes)),
            200,
          );
        }
        return http.Response('{}', 404);
      }),
    );
    harness.configure();
    await openGraph(tester, harness);

    final viewer = tester.widget<InteractiveViewer>(find.byType(InteractiveViewer));
    expect(viewer.constrained, isFalse);
    expect(viewer.minScale, kGraphMinScale);
    expect(viewer.maxScale, kGraphMaxScale);

    final viewerBox = tester.renderObject<RenderBox>(find.byType(InteractiveViewer));
    final viewportWidth = viewerBox.size.width;
    final viewportHeight = viewerBox.size.height;
    expect(viewportWidth, greaterThan(0));

    final canvasFinder = find.descendant(
      of: find.byType(InteractiveViewer),
      matching: find.byWidgetPredicate(
        (widget) => widget is SizedBox && widget.child is Stack,
      ),
    );
    final canvasSize = tester.getSize(canvasFinder);
    expect(canvasSize.width, greaterThan(viewportWidth));
    expect(canvasSize.height, greaterThan(viewportHeight));

    expect(harness.graph.selectedObjectId, isNull);

    await tester.tap(find.byTooltip('Fit graph'));
    await tester.pumpAndSettle();

    final distantNode = find.text('Wide graph 11');
    await tester.ensureVisible(distantNode);
    await tester.tap(distantNode);
    await tester.pumpAndSettle();

    expect(harness.graph.selectedObjectId, 'wide-11');
  });

  testWidgets('Details edit refreshes rooted workspace', (tester) async {
    tester.view.physicalSize = const Size(1280, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    var graphCalls = 0;
    var rootedRefreshed = false;
    final harness = GraphTestHarness(
      MockClient((request) async {
        if (request.url.path == '/notifications') {
          return http.Response(jsonEncode({'notifications': []}), 200);
        }
        if (request.url.path == '/today') {
          return http.Response(
            jsonEncode({
              'date': '2026-08-28',
              'timezone': 'Europe/Amsterdam',
              'day_start': '2026-08-28T00:00:00+02:00',
              'tasks': [],
              'calendar_events': [],
              'notifications': [],
            }),
            200,
          );
        }
        if (request.url.path == '/graph/workspace') {
          graphCalls += 1;
          final root = request.url.queryParameters['root_id'];
          if (root == 'task-a') {
            return http.Response(
              jsonEncode(
                _workspaceJson(
                  rootId: 'task-a',
                  nodes: [
                    _objectJson(
                      id: 'task-a',
                      title: rootedRefreshed ? 'Renamed A' : 'Task A',
                    ),
                  ],
                ),
              ),
              200,
            );
          }
          return http.Response(
            jsonEncode(
              _workspaceJson(
                nodes: [_objectJson(id: 'task-a', title: 'Task A')],
              ),
            ),
            200,
          );
        }
        if (request.url.path == '/objects/task-a') {
          return http.Response(
            jsonEncode(_objectJson(id: 'task-a', title: 'Task A')),
            200,
          );
        }
        if (request.url.path == '/objects/task-a/neighbors') {
          return http.Response(
            jsonEncode({'object_id': 'task-a', 'neighbors': []}),
            200,
          );
        }
        if (request.url.path == '/objects/task-a/context') {
          return http.Response(
            jsonEncode({
              'object': _objectJson(id: 'task-a', title: 'Task A'),
              'edges': [],
              'neighbors': [],
            }),
            200,
          );
        }
        if (request.method == 'PATCH' && request.url.path == '/tasks/task-a') {
          rootedRefreshed = true;
          return http.Response(
            jsonEncode({
              'object': _objectJson(id: 'task-a', title: 'Renamed A'),
            }),
            200,
          );
        }
        return http.Response('{}', 404);
      }),
    );
    harness.configure();
    await openGraph(tester, harness);

    await harness.graph.reRoot('task-a');
    await tester.pumpAndSettle();

    harness.graph.selectObject('task-a');
    await tester.pump();

    await tester.tap(find.text('Details'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Edit'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, 'Renamed A');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    await tester.pageBack();
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));

    expect(harness.graph.rootId, 'task-a');
    expect(find.text('Renamed A'), findsWidgets);
    expect(graphCalls, greaterThanOrEqualTo(3));
  });

  testWidgets('Details delete refreshes overview without deleted task', (tester) async {
    tester.view.physicalSize = const Size(1280, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    var overviewCalls = 0;
    final harness = GraphTestHarness(
      MockClient((request) async {
        if (request.url.path == '/notifications') {
          return http.Response(jsonEncode({'notifications': []}), 200);
        }
        if (request.url.path == '/today') {
          return http.Response(
            jsonEncode({
              'date': '2026-08-28',
              'timezone': 'Europe/Amsterdam',
              'day_start': '2026-08-28T00:00:00+02:00',
              'tasks': [],
              'calendar_events': [],
              'notifications': [],
            }),
            200,
          );
        }
        if (request.url.path == '/graph/workspace' &&
            request.url.queryParameters['root_id'] == null) {
          overviewCalls += 1;
          final nodes = overviewCalls == 1
              ? [
                  _objectJson(id: 'task-a', title: 'Task A'),
                  _objectJson(id: 'task-b', title: 'Task B'),
                ]
              : [_objectJson(id: 'task-b', title: 'Task B')];
          return http.Response(jsonEncode(_workspaceJson(nodes: nodes)), 200);
        }
        if (request.url.path == '/objects/task-a') {
          return http.Response(
            jsonEncode(_objectJson(id: 'task-a', title: 'Task A')),
            200,
          );
        }
        if (request.url.path == '/objects/task-a/neighbors') {
          return http.Response(
            jsonEncode({'object_id': 'task-a', 'neighbors': []}),
            200,
          );
        }
        if (request.url.path == '/objects/task-a/context') {
          return http.Response(
            jsonEncode({
              'object': _objectJson(id: 'task-a', title: 'Task A'),
              'edges': [],
              'neighbors': [],
            }),
            200,
          );
        }
        if (request.method == 'DELETE' && request.url.path == '/tasks/task-a') {
          return http.Response(
            jsonEncode({
              'object': _objectJson(id: 'task-a', title: 'Task A', status: 'deleted'),
              'new_status': 'deleted',
            }),
            200,
          );
        }
        return http.Response('{}', 404);
      }),
    );
    harness.configure();
    await openGraph(tester, harness);

    harness.graph.selectObject('task-a');
    await tester.pump();

    await tester.tap(find.text('Details'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Delete'));
    await tester.pumpAndSettle();
    await tester.tap(
      find.descendant(
        of: find.byType(AlertDialog),
        matching: find.widgetWithText(FilledButton, 'Delete'),
      ),
    );
    await tester.pumpAndSettle();

    await tester.pageBack();
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));

    expect(harness.graph.rootId, isNull);
    expect(find.text('Task A'), findsNothing);
    expect(find.text('Task B'), findsOneWidget);
    expect(overviewCalls, greaterThanOrEqualTo(2));
  });

  testWidgets('Details delete current root falls back to overview', (tester) async {
    tester.view.physicalSize = const Size(1280, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    var rootedCalls = 0;
    var overviewCalls = 0;
    final harness = GraphTestHarness(
      MockClient((request) async {
        if (request.url.path == '/notifications') {
          return http.Response(jsonEncode({'notifications': []}), 200);
        }
        if (request.url.path == '/today') {
          return http.Response(
            jsonEncode({
              'date': '2026-08-28',
              'timezone': 'Europe/Amsterdam',
              'day_start': '2026-08-28T00:00:00+02:00',
              'tasks': [],
              'calendar_events': [],
              'notifications': [],
            }),
            200,
          );
        }
        if (request.url.path == '/graph/workspace') {
          final root = request.url.queryParameters['root_id'];
          if (root == 'task-a') {
            rootedCalls += 1;
            if (rootedCalls == 1) {
              return http.Response(
                jsonEncode(
                  _workspaceJson(
                    rootId: 'task-a',
                    nodes: [_objectJson(id: 'task-a', title: 'Task A')],
                  ),
                ),
                200,
              );
            }
            return http.Response('{"detail":"not found"}', 404);
          }
          overviewCalls += 1;
          final nodes = overviewCalls == 1
              ? [_objectJson(id: 'task-a', title: 'Task A')]
              : [_objectJson(id: 'task-b', title: 'Task B')];
          return http.Response(jsonEncode(_workspaceJson(nodes: nodes)), 200);
        }
        if (request.url.path == '/objects/task-a') {
          return http.Response(
            jsonEncode(_objectJson(id: 'task-a', title: 'Task A')),
            200,
          );
        }
        if (request.url.path == '/objects/task-a/neighbors') {
          return http.Response(
            jsonEncode({'object_id': 'task-a', 'neighbors': []}),
            200,
          );
        }
        if (request.url.path == '/objects/task-a/context') {
          return http.Response(
            jsonEncode({
              'object': _objectJson(id: 'task-a', title: 'Task A'),
              'edges': [],
              'neighbors': [],
            }),
            200,
          );
        }
        if (request.method == 'DELETE' && request.url.path == '/tasks/task-a') {
          return http.Response(
            jsonEncode({
              'object': _objectJson(id: 'task-a', title: 'Task A', status: 'deleted'),
              'new_status': 'deleted',
            }),
            200,
          );
        }
        return http.Response('{}', 404);
      }),
    );
    harness.configure();
    await openGraph(tester, harness);

    await harness.graph.reRoot('task-a');
    await tester.pumpAndSettle();

    harness.graph.selectObject('task-a');
    await tester.pump();

    await tester.tap(find.text('Details'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Delete'));
    await tester.pumpAndSettle();
    await tester.tap(
      find.descendant(
        of: find.byType(AlertDialog),
        matching: find.widgetWithText(FilledButton, 'Delete'),
      ),
    );
    await tester.pumpAndSettle();

    await tester.pageBack();
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));

    expect(harness.graph.rootId, isNull);
    expect(find.text('Task A'), findsNothing);
    expect(find.text('Task B'), findsOneWidget);
    expect(rootedCalls, greaterThanOrEqualTo(2));
    expect(overviewCalls, greaterThanOrEqualTo(2));
  });
}
