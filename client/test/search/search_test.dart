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
    await tester.tap(find.widgetWithText(FilledButton, 'Поиск'));
    await tester.pumpAndSettle();

    expect(find.text('Alpha task'), findsOneWidget);
    expect(find.text('pending'), findsOneWidget);
  });

  testWidgets('search provider filter sends canonical provider value', (tester) async {
    await tester.pumpWidget(
      buildSearch(MockClient((request) async {
        if (request.url.path == '/search') {
          expect(request.url.queryParameters['provider'], 'gmail');
          return http.Response('[]', 200);
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, 'mail');
    final providerDropdown = find.byType(DropdownButtonFormField<String?>).last;
    await tester.tap(providerDropdown);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Gmail').last);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Поиск'));
    await tester.pumpAndSettle();
  });

  testWidgets('search shows Russian provider label and date', (tester) async {
    await tester.pumpWidget(
      buildSearch(MockClient((request) async {
        if (request.url.path == '/search') {
          return http.Response.bytes(
            utf8.encode(jsonEncode([
              {
                'id': 'email-1',
                'kind': 'email',
                'title': 'Письмо от преподавателя',
                'body': 'Короткий фрагмент',
                'provider': 'gmail',
                'external_id': null,
                'canonical_uri': null,
                'status': null,
                'start_at': null,
                'due_at': null,
                'occurred_at': '2026-08-30T15:43:00Z',
                'metadata': {},
                'origin': 'source',
                'state': 'observed',
                'confidence': null,
                'created_at': '2026-08-28T08:00:00Z',
                'updated_at': '2026-08-28T08:00:00Z',
              },
            ])),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'},
          );
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, 'письмо');
    await tester.tap(find.widgetWithText(FilledButton, 'Поиск'));
    await tester.pumpAndSettle();

    expect(find.text('Письмо от преподавателя'), findsOneWidget);
    expect(find.textContaining('Gmail'), findsOneWidget);
    expect(find.textContaining('30.08.2026'), findsOneWidget);
    expect(find.text('По релевантности'), findsOneWidget);
    expect(find.text('Показано: 1'), findsOneWidget);
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
    await tester.tap(find.widgetWithText(FilledButton, 'Поиск'));
    await tester.pumpAndSettle();
    expect(find.text('Ничего не найдено'), findsOneWidget);
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
    await tester.tap(find.widgetWithText(FilledButton, 'Поиск'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(auth.status, AuthStatus.needsAuth);
  });
}
