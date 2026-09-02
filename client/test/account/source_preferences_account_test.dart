import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/account/account_screen.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/auth/token_store.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'account_test_helpers.dart';

const _baseUrl = 'https://secretary.example';
const _token = 'opaque-test-token';

AuthController _buildAuth(SecretaryApiClient apiClient) {
  final auth = AuthController(
    apiClient: apiClient,
    tokenStore: FakeTokenStore(),
    serverUrlStore: FakeServerUrlStore(),
  );
  auth.status = AuthStatus.authenticated;
  auth.user = UserMe(
    id: 'user-1',
    displayName: 'Alice',
    createdAt: '2026-01-01T00:00:00Z',
  );
  return auth;
}

Finder _gmailSourceRowFinder() =>
    find.byKey(const Key('source-preference-gmail'));

Finder _gmailSwitchFinder() {
  return find.descendant(
    of: _gmailSourceRowFinder(),
    matching: find.byType(Switch),
  );
}

Finder _gmailCadenceDropdownFinder() {
  return find.descendant(
    of: _gmailSourceRowFinder(),
    matching: find.byType(DropdownButton<int>),
  );
}

Finder _mattermostSourceRowFinder() =>
    find.byKey(const Key('source-preference-mattermost'));

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('Account source preferences UI', () {
    testWidgets('renders Синхронизация and five source labels', (tester) async {
      final client = buildAccountApiClient();
      await pumpAccountReady(
        tester,
        buildAccountScreen(
            apiClient: client, authController: _buildAuth(client)),
      );

      expect(find.text('Синхронизация'), findsOneWidget);
      expect(find.byKey(const Key('source-preference-gmail')), findsOneWidget);
      expect(
        find.byKey(const Key('source-preference-google_calendar')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('source-preference-yandex_mail')), findsOneWidget);
      expect(
        find.byKey(const Key('source-preference-yandex_calendar')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('source-preference-mattermost')), findsOneWidget);
    });

    testWidgets('disconnected source remains visible with Не подключено',
        (tester) async {
      final client = buildAccountApiClient(
        connectionsJson: accountConnectionsJson(
          googleConnected: false,
          gmailAvailable: false,
          calendarAvailable: false,
        ),
      );
      await pumpAccountReady(
        tester,
        buildAccountScreen(
            apiClient: client, authController: _buildAuth(client)),
      );

      expect(find.text('Gmail'), findsOneWidget);
      expect(find.text('Не подключено'), findsWidgets);
    });

    testWidgets('Gmail OFF sends exactly enabled false', (tester) async {
      Map<String, dynamic>? capturedBody;
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.method == 'PATCH' &&
              request.url.path.endsWith('/me/source-preferences/gmail')) {
            capturedBody =
                jsonDecode(request.body as String) as Map<String, dynamic>;
            return http.Response(
              jsonEncode({
                'source': 'gmail',
                'enabled': false,
                'sync_interval_seconds': 300,
                'default_sync_interval_seconds': 300,
                'min_sync_interval_seconds': 60,
                'max_sync_interval_seconds': 86400,
              }),
              200,
            );
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await pumpAccountReady(
        tester,
        buildAccountScreen(
            apiClient: client, authController: _buildAuth(client)),
      );

      await tester.tap(_gmailSwitchFinder());
      await tester.pump();
      for (var i = 0; i < 30; i++) {
        await tester.pump(const Duration(milliseconds: 50));
        if (capturedBody != null) {
          break;
        }
      }

      expect(capturedBody, {'enabled': false});
    });

    testWidgets('successful toggle updates UI', (tester) async {
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.method == 'PATCH' &&
              request.url.path.endsWith('/me/source-preferences/gmail')) {
            return http.Response(
              jsonEncode({
                'source': 'gmail',
                'enabled': false,
                'sync_interval_seconds': 300,
                'default_sync_interval_seconds': 300,
                'min_sync_interval_seconds': 60,
                'max_sync_interval_seconds': 86400,
              }),
              200,
            );
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await pumpAccountReady(
        tester,
        buildAccountScreen(
            apiClient: client, authController: _buildAuth(client)),
      );

      await tester.tap(_gmailSwitchFinder());
      await tester.pumpAndSettle();

      expect(
        find.descendant(
          of: _gmailSourceRowFinder(),
          matching: find.byWidgetPredicate(
            (widget) => widget is Switch && widget.value == false,
          ),
        ),
        findsOneWidget,
      );
    });

    testWidgets('failed toggle preserves old value and shows error',
        (tester) async {
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.method == 'PATCH' &&
              request.url.path.endsWith('/me/source-preferences/gmail')) {
            return http.Response(jsonEncode({'detail': 'toggle failed'}), 422);
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await pumpAccountReady(
        tester,
        buildAccountScreen(
            apiClient: client, authController: _buildAuth(client)),
      );

      await tester.tap(_gmailSwitchFinder());
      await tester.pumpAndSettle();

      expect(
        find.descendant(
          of: _gmailSourceRowFinder(),
          matching: find.byWidgetPredicate(
            (widget) => widget is Switch && widget.value == true,
          ),
        ),
        findsOneWidget,
      );
      expect(find.text('toggle failed'), findsOneWidget);
    });

    testWidgets('cadence PATCH does not include enabled', (tester) async {
      Map<String, dynamic>? capturedBody;
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.method == 'PATCH' &&
              request.url.path.endsWith('/me/source-preferences/gmail')) {
            capturedBody =
                jsonDecode(request.body as String) as Map<String, dynamic>;
            return http.Response(
              jsonEncode({
                'source': 'gmail',
                'enabled': true,
                'sync_interval_seconds': 120,
                'default_sync_interval_seconds': 300,
                'min_sync_interval_seconds': 60,
                'max_sync_interval_seconds': 86400,
              }),
              200,
            );
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await pumpAccountReady(
        tester,
        buildAccountScreen(
          apiClient: client,
          authController: _buildAuth(client),
          sourcePreferencesJson: accountSourcePreferencesJson(),
        ),
      );

      await tester.tap(_gmailCadenceDropdownFinder());
      await tester.pumpAndSettle();
      await tester.tap(find.text('2 мин').last);
      await tester.pump();
      for (var i = 0; i < 30; i++) {
        await tester.pump(const Duration(milliseconds: 50));
        if (capturedBody != null) {
          break;
        }
      }

      expect(capturedBody, {'sync_interval_seconds': 120});
      expect(capturedBody!.containsKey('enabled'), isFalse);
    });

    testWidgets('reset sends explicit null fields', (tester) async {
      Map<String, dynamic>? capturedBody;
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.method == 'PATCH' &&
              request.url.path.endsWith('/me/source-preferences/gmail')) {
            capturedBody =
                jsonDecode(request.body as String) as Map<String, dynamic>;
            return http.Response(
              jsonEncode({
                'source': 'gmail',
                'enabled': true,
                'sync_interval_seconds': 300,
                'default_sync_interval_seconds': 300,
                'min_sync_interval_seconds': 60,
                'max_sync_interval_seconds': 86400,
              }),
              200,
            );
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await pumpAccountReady(
        tester,
        buildAccountScreen(
            apiClient: client, authController: _buildAuth(client)),
      );

      await tester.tap(
        find.descendant(
          of: _gmailSourceRowFinder(),
          matching: find.text('По умолчанию'),
        ),
      );
      await tester.pump();
      for (var i = 0; i < 30; i++) {
        await tester.pump(const Duration(milliseconds: 50));
        if (capturedBody != null) {
          break;
        }
      }

      expect(capturedBody, {
        'enabled': null,
        'sync_interval_seconds': null,
      });
    });

    testWidgets('Gmail saving does not disable Mattermost controls',
        (tester) async {
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.method == 'PATCH' &&
              request.url.path.endsWith('/me/source-preferences/gmail')) {
            await Future<void>.delayed(const Duration(milliseconds: 200));
            return http.Response(
              jsonEncode({
                'source': 'gmail',
                'enabled': false,
                'sync_interval_seconds': 300,
                'default_sync_interval_seconds': 300,
                'min_sync_interval_seconds': 60,
                'max_sync_interval_seconds': 86400,
              }),
              200,
            );
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await pumpAccountReady(
        tester,
        buildAccountScreen(
            apiClient: client, authController: _buildAuth(client)),
      );

      await tester.tap(_gmailSwitchFinder());
      await tester.pump(const Duration(milliseconds: 50));

      final mattermostSwitch = find.descendant(
        of: _mattermostSourceRowFinder(),
        matching: find.byType(Switch),
      );
      expect(tester.widget<Switch>(mattermostSwitch).onChanged, isNotNull);

      await tester.pumpAndSettle();
    });

    testWidgets('auth failure uses existing logout handling', (tester) async {
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.method == 'PATCH' &&
              request.url.path.endsWith('/me/source-preferences/gmail')) {
            return http.Response(jsonEncode({'detail': 'Unauthorized'}), 401);
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);
      final auth = _buildAuth(client);

      await pumpAccountReady(
        tester,
        buildAccountScreen(apiClient: client, authController: auth),
      );

      await tester.tap(_gmailSwitchFinder());
      await tester.pumpAndSettle();

      expect(auth.status, AuthStatus.needsAuth);
    });
  });
}
