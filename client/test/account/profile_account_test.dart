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

Map<String, dynamic> _connectionsJson() {
  return {
    'google': {
      'connected': false,
      'email': null,
      'gmail_available': false,
      'calendar_available': false,
      'drive_available': false,
    },
    'yandex_mail': {'connected': false, 'email': null},
    'yandex_calendar': {'connected': false, 'email': null},
    'mattermost': [],
  };
}

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

Future<void> _pumpAccountReady(WidgetTester tester, Widget child) async {
  await pumpAccountReady(tester, child);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('Account profile and settings UX', () {
    testWidgets('shows Профиль, ИИ and Подключения sections', (tester) async {
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.url.path.endsWith('/connections')) {
            return http.Response(jsonEncode(_connectionsJson()), 200);
          }
          if (isAccountSettingsRequest(request.url)) {
            return http.Response(jsonEncode(accountSettingsJson()), 200);
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await _pumpAccountReady(
        tester,
        buildAccountScreen(apiClient: client, authController: _buildAuth(client)),
      );

      expect(find.text('Профиль'), findsOneWidget);
      expect(find.text('Моя идентичность'), findsOneWidget);
      expect(find.text('ИИ'), findsOneWidget);
      expect(find.text('Подключения'), findsOneWidget);
      expect(find.text('Добавить файл'), findsNothing);
      expect(find.text('Добавить папку'), findsNothing);
    });

    testWidgets('display name save sends PATCH /me', (tester) async {
      String? patchedName;
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.url.path.endsWith('/connections')) {
            return http.Response(jsonEncode(_connectionsJson()), 200);
          }
          if (isAccountSettingsRequest(request.url)) {
            return http.Response(jsonEncode(accountSettingsJson()), 200);
          }
          if (request.url.path.endsWith('/me') && request.method == 'PATCH') {
            final body = jsonDecode(request.body) as Map<String, dynamic>;
            patchedName = body['display_name'] as String;
            return http.Response(
              jsonEncode({
                'id': 'user-1',
                'display_name': patchedName,
                'created_at': '2026-01-01T00:00:00Z',
              }),
              200,
            );
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await _pumpAccountReady(
        tester,
        buildAccountScreen(apiClient: client, authController: _buildAuth(client)),
      );

      await tester.enterText(find.widgetWithText(TextField, 'Отображаемое имя'), 'Bob');
      await tester.tap(find.text('Сохранить имя'));
      await tester.pumpAndSettle();

      expect(patchedName, 'Bob');
    });

    testWidgets('timezone save sends PATCH /me/settings', (tester) async {
      String? patchedTimezone;
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.url.path.endsWith('/connections')) {
            return http.Response(jsonEncode(_connectionsJson()), 200);
          }
          if (request.url.path.endsWith('/me/settings') && request.method == 'PATCH') {
            final body = jsonDecode(request.body) as Map<String, dynamic>;
            patchedTimezone = body['timezone'] as String;
            return http.Response(
              jsonEncode(
                accountSettingsJson(timezone: patchedTimezone!),
              ),
              200,
            );
          }
          if (isAccountSettingsRequest(request.url)) {
            return http.Response(jsonEncode(accountSettingsJson()), 200);
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await _pumpAccountReady(
        tester,
        buildAccountScreen(apiClient: client, authController: _buildAuth(client)),
      );

      await tester.enterText(
        find.widgetWithText(TextField, 'Часовой пояс (IANA)'),
        'Europe/Moscow',
      );
      await tester.tap(find.text('Сохранить часовой пояс'));
      await tester.pumpAndSettle();

      expect(patchedTimezone, 'Europe/Moscow');
    });

    testWidgets('invalid setting error shown locally', (tester) async {
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.url.path.endsWith('/connections')) {
            return http.Response(jsonEncode(_connectionsJson()), 200);
          }
          if (request.url.path.endsWith('/me/settings') && request.method == 'PATCH') {
            return http.Response(jsonEncode({'detail': 'invalid timezone'}), 422);
          }
          if (isAccountSettingsRequest(request.url)) {
            return http.Response(jsonEncode(accountSettingsJson()), 200);
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await _pumpAccountReady(
        tester,
        buildAccountScreen(apiClient: client, authController: _buildAuth(client)),
      );

      await tester.enterText(
        find.widgetWithText(TextField, 'Часовой пояс (IANA)'),
        'Bad/Zone',
      );
      await tester.tap(find.text('Сохранить часовой пояс'));
      for (var i = 0; i < 40; i++) {
        await tester.pump(const Duration(milliseconds: 50));
        if (find.textContaining('invalid timezone').evaluate().isNotEmpty) {
          break;
        }
      }

      expect(find.textContaining('invalid timezone'), findsOneWidget);
    });

    testWidgets('OpenAI key dialog obscures input and PUT credential', (tester) async {
      String? submittedKey;
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.url.path.endsWith('/connections')) {
            return http.Response(jsonEncode(_connectionsJson()), 200);
          }
          if (request.url.path.endsWith('/me/credentials/openai') && request.method == 'PUT') {
            final body = jsonDecode(request.body) as Map<String, dynamic>;
            submittedKey = body['api_key'] as String;
            return http.Response(jsonEncode({'configured': true}), 200);
          }
          if (isAccountSettingsRequest(request.url)) {
            return http.Response(jsonEncode(accountSettingsJson()), 200);
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await _pumpAccountReady(
        tester,
        buildAccountScreen(apiClient: client, authController: _buildAuth(client)),
      );

      await tester.tap(find.text('Установить ключ'));
      await tester.pumpAndSettle();

      final keyField = tester.widget<TextField>(find.widgetWithText(TextField, 'API key'));
      expect(keyField.obscureText, isTrue);

      await tester.enterText(find.widgetWithText(TextField, 'API key'), 'sk-test-key');
      await tester.tap(find.text('Установить'));
      await tester.pumpAndSettle();

      expect(submittedKey, 'sk-test-key');
      expect(find.text('sk-test-key'), findsNothing);
    });

    testWidgets('configured OpenAI key state displayed', (tester) async {
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.url.path.endsWith('/connections')) {
            return http.Response(jsonEncode(_connectionsJson()), 200);
          }
          if (isAccountSettingsRequest(request.url)) {
            return http.Response(
              jsonEncode(accountSettingsJson(openaiKeyConfigured: true)),
              200,
            );
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await _pumpAccountReady(
        tester,
        buildAccountScreen(
          apiClient: client,
          authController: _buildAuth(client),
          settingsJson: accountSettingsJson(openaiKeyConfigured: true),
        ),
      );

      expect(find.text('OpenAI API key: настроен'), findsOneWidget);
      expect(find.text('Заменить ключ'), findsOneWidget);
      expect(find.text('Удалить ключ'), findsOneWidget);
    });

    testWidgets('delete key sends DELETE /me/credentials/openai', (tester) async {
      var deleteCalled = false;
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.url.path.endsWith('/connections')) {
            return http.Response(jsonEncode(_connectionsJson()), 200);
          }
          if (request.url.path.endsWith('/me/credentials/openai') && request.method == 'DELETE') {
            deleteCalled = true;
            return http.Response(jsonEncode({'configured': false}), 200);
          }
          if (isAccountSettingsRequest(request.url)) {
            return http.Response(
              jsonEncode(accountSettingsJson(openaiKeyConfigured: true)),
              200,
            );
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await _pumpAccountReady(
        tester,
        buildAccountScreen(
          apiClient: client,
          authController: _buildAuth(client),
          settingsJson: accountSettingsJson(openaiKeyConfigured: true),
        ),
      );

      await tester.tap(find.text('Удалить ключ'));
      await tester.pumpAndSettle();

      expect(deleteCalled, isTrue);
    });

    testWidgets('model dropdown uses only server-provided allowed choices', (tester) async {
      final client = buildAccountApiClient(
        settingsJson: accountSettingsJson(
          assistantModel: 'gpt-5.6-luna',
          allowedAssistantModels: ['gpt-5.6-luna', 'gpt-5.6-terra'],
        ),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await _pumpAccountReady(
        tester,
        buildAccountScreen(apiClient: client, authController: _buildAuth(client)),
      );

      expect(find.text('gpt-5.6-luna'), findsWidgets);

      await tester.tap(find.byType(DropdownButton<String>).first);
      await tester.pumpAndSettle();

      expect(find.text('gpt-5.6-terra'), findsOneWidget);
    });

    testWidgets('inconsistent model and allowlist does not crash Account', (tester) async {
      final client = buildAccountApiClient(
        settingsJson: accountSettingsJson(
          assistantModel: 'gpt-disallowed',
          allowedAssistantModels: ['gpt-5.6-luna'],
        ),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await _pumpAccountReady(
        tester,
        buildAccountScreen(apiClient: client, authController: _buildAuth(client)),
      );

      expect(find.text('Модель Assistant'), findsOneWidget);
      expect(find.text('gpt-5.6-luna'), findsWidgets);
      expect(find.text('gpt-disallowed'), findsNothing);
    });
  });

  group('Identity profile UX', () {
    const existingProfile = '''Имя: Дмитрий Яценко
Как ко мне обращаться: Дмитрий
Варианты имени: Яценко
''';

    testWidgets('loads existing identity profile text unchanged', (tester) async {
      final client = buildAccountApiClient();
      client.configure(baseUrl: _baseUrl, token: _token);

      await _pumpAccountReady(
        tester,
        buildAccountScreen(
          apiClient: client,
          authController: _buildAuth(client),
          identityJson: accountIdentityJson(profileText: existingProfile),
        ),
      );

      expect(find.text('Моя идентичность'), findsOneWidget);
      final field = tester.widget<TextField>(
        find.byKey(const Key('identity_profile_text')),
      );
      expect(field.controller?.text, existingProfile);
    });

    testWidgets('save sends exact structured text via PUT /me/identity', (tester) async {
      String? savedProfileText;
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.url.path.endsWith('/connections')) {
            return http.Response(jsonEncode(_connectionsJson()), 200);
          }
          if (isAccountSettingsRequest(request.url)) {
            return http.Response(jsonEncode(accountSettingsJson()), 200);
          }
          if (isAccountSourcePreferencesRequest(request.url)) {
            return http.Response(jsonEncode(accountSourcePreferencesJson()), 200);
          }
          if (isAccountIdentityRequest(request.url) && request.method == 'GET') {
            return http.Response(jsonEncode(accountIdentityJson()), 200);
          }
          if (isAccountIdentityRequest(request.url) && request.method == 'PUT') {
            final body = jsonDecode(request.body) as Map<String, dynamic>;
            savedProfileText = body['profile_text'] as String;
            return http.Response.bytes(
              utf8.encode(jsonEncode(accountIdentityJson(profileText: savedProfileText!))),
              200,
              headers: {'content-type': 'application/json; charset=utf-8'},
            );
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await _pumpAccountReady(
        tester,
        AccountScreen(
          apiClient: client,
          authController: _buildAuth(client),
        ),
      );
      await tester.pumpAndSettle();

      const edited = '''Имя: Тест Пользователь
Email:
- test@example.com
''';
      await tester.enterText(find.byKey(const Key('identity_profile_text')), edited);
      await tester.tap(find.text('Сохранить идентичность'));
      await tester.pumpAndSettle();

      expect(savedProfileText, edited);
    });

    testWidgets('save failure keeps edits and shows error', (tester) async {
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          if (request.url.path.endsWith('/connections')) {
            return http.Response(jsonEncode(_connectionsJson()), 200);
          }
          if (isAccountSettingsRequest(request.url)) {
            return http.Response(jsonEncode(accountSettingsJson()), 200);
          }
          if (isAccountSourcePreferencesRequest(request.url)) {
            return http.Response(jsonEncode(accountSourcePreferencesJson()), 200);
          }
          if (isAccountIdentityRequest(request.url) && request.method == 'GET') {
            return http.Response(jsonEncode(accountIdentityJson()), 200);
          }
          if (isAccountIdentityRequest(request.url) && request.method == 'PUT') {
            return http.Response(
              jsonEncode({'detail': 'profile_text exceeds maximum length'}),
              422,
            );
          }
          return http.Response('{}', 404);
        }),
      );
      client.configure(baseUrl: _baseUrl, token: _token);

      await _pumpAccountReady(
        tester,
        AccountScreen(
          apiClient: client,
          authController: _buildAuth(client),
        ),
      );
      await tester.pumpAndSettle();

      const edited = 'Имя: Ошибка сохранения';
      await tester.enterText(find.byKey(const Key('identity_profile_text')), edited);
      await tester.tap(find.text('Сохранить идентичность'));
      await tester.pumpAndSettle();

      final field = tester.widget<TextField>(
        find.byKey(const Key('identity_profile_text')),
      );
      expect(field.controller?.text, edited);
      expect(find.textContaining('profile_text exceeds maximum length'), findsOneWidget);
    });

    testWidgets('empty identity profile is safe', (tester) async {
      final client = buildAccountApiClient();
      client.configure(baseUrl: _baseUrl, token: _token);

      await _pumpAccountReady(
        tester,
        buildAccountScreen(
          apiClient: client,
          authController: _buildAuth(client),
          identityJson: accountIdentityJson(profileText: ''),
        ),
      );

      final field = tester.widget<TextField>(
        find.byKey(const Key('identity_profile_text')),
      );
      expect(field.controller?.text, '');
      expect(find.text('Сохранить идентичность'), findsOneWidget);
    });
  });
}

class FakeTokenStore implements TokenStore {
  @override
  Future<String?> readToken() async => _token;

  @override
  Future<void> writeToken(String token) async {}

  @override
  Future<void> deleteToken() async {}
}

class FakeServerUrlStore implements ServerUrlStore {
  @override
  Future<String?> readServerUrl() async => _baseUrl;

  @override
  Future<void> writeServerUrl(String url) async {}

  @override
  Future<void> deleteServerUrl() async {}
}
