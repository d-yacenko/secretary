import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/auth/token_store.dart';
import 'package:personal_secretary/capture/capture_controller.dart';
import 'package:personal_secretary/search/search_screen.dart';

void main() {
  const baseUrl = 'https://secretary.example';
  const token = 'search-token';

  Widget buildSearch(MockClient mock) {
    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    return MaterialApp(
      home: Scaffold(
        body: SearchScreen(
          apiClient: apiClient,
          authController: auth,
          captureController: CaptureController(
            apiClient: apiClient,
            authController: auth,
          ),
        ),
      ),
    );
  }

  testWidgets('search sends GET /search and renders results', (tester) async {
    await tester.pumpWidget(
      buildSearch(MockClient((request) async {
        if (request.url.path == '/search') {
          expect(request.url.queryParameters['q'], 'alpha task');
          return http.Response(
            jsonEncode([
              {
                'id': 'task-1',
                'kind': 'task',
                'title': 'Alpha task',
                'body': 'Long body text that should be bounded in UI',
                'provider': null,
                'external_id': null,
                'canonical_uri': null,
                'status': 'pending',
                'start_at': null,
                'due_at': null,
                'metadata': {},
                'origin': 'user',
                'state': 'confirmed',
                'confidence': null,
                'created_at': '2026-08-28T08:00:00Z',
                'updated_at': '2026-08-28T08:00:00Z',
              },
            ]),
            200,
          );
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, 'alpha task');
    await tester.tap(find.widgetWithText(FilledButton, 'Search'));
    await tester.pumpAndSettle();

    expect(find.text('Alpha task'), findsOneWidget);
    expect(find.text('Status: pending'), findsOneWidget);
  });

  testWidgets('search empty state', (tester) async {
    await tester.pumpWidget(
      buildSearch(MockClient((request) async {
        if (request.url.path == '/search') {
          return http.Response('[]', 200);
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, 'nothing');
    await tester.tap(find.widgetWithText(FilledButton, 'Search'));
    await tester.pumpAndSettle();
    expect(find.text('No results'), findsOneWidget);
  });

  testWidgets('search 401 exits authenticated UI', (tester) async {
    final apiClient = SecretaryApiClient(
      httpClient: MockClient((request) async {
        return http.Response('{"detail":"unauthorized"}', 401);
      }),
    );
    apiClient.configure(baseUrl: baseUrl, token: token);
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SearchScreen(
            apiClient: apiClient,
            authController: auth,
            captureController: CaptureController(
              apiClient: apiClient,
              authController: auth,
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, 'x');
    await tester.tap(find.widgetWithText(FilledButton, 'Search'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(auth.status, AuthStatus.needsAuth);
  });
}
