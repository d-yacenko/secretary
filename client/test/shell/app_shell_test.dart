import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/auth/token_store.dart';
import 'package:personal_secretary/capture/capture_controller.dart';
import 'package:personal_secretary/shell/app_shell.dart';

const _baseUrl = 'https://secretary.example';
const _token = 'shell-token';

MockClient shellMockClient() {
  return MockClient((request) async {
    if (request.url.path == '/notifications') {
      return http.Response(jsonEncode({'notifications': []}), 200);
    }
    if (request.url.path == '/today') {
      return http.Response(
        jsonEncode({
          'date': '2026-08-28',
          'timezone': 'Europe/Amsterdam',
          'tasks': [],
          'calendar_events': [],
          'notifications': [],
        }),
        200,
      );
    }
    return http.Response('{}', 404);
  });
}

AuthController buildAuth() {
  final apiClient = SecretaryApiClient(httpClient: shellMockClient());
  apiClient.configure(baseUrl: _baseUrl, token: _token);
  final auth = AuthController(
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
  return auth;
}

void main() {
  testWidgets('narrow layout exposes five destinations and Capture FAB', (tester) async {
    tester.view.physicalSize = const Size(400, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final auth = buildAuth();
    final capture = CaptureController(
      apiClient: auth.apiClient,
      authController: auth,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: AppShell(authController: auth, captureController: capture),
      ),
    );
    await tester.pumpAndSettle();

    for (final label in ['Inbox', 'Today', 'Graph', 'Search', 'Assistant']) {
      expect(find.text(label), findsWidgets);
    }
    expect(find.text('Capture'), findsOneWidget);
    expect(find.byType(NavigationBar), findsOneWidget);
  });

  testWidgets('wide layout exposes NavigationRail and prominent Capture action', (tester) async {
    tester.view.physicalSize = const Size(900, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final auth = buildAuth();
    final capture = CaptureController(
      apiClient: auth.apiClient,
      authController: auth,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: AppShell(authController: auth, captureController: capture),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(NavigationRail), findsOneWidget);
    expect(find.text('Capture'), findsOneWidget);
    expect(find.byType(FloatingActionButton), findsNothing);
  });
}
