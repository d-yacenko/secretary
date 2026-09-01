import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/account/account_screen.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';

Map<String, dynamic> accountConnectionsJson({
  bool googleConnected = true,
  bool gmailAvailable = true,
  bool calendarAvailable = true,
  bool driveAvailable = false,
  List<Map<String, dynamic>> mattermost = const [],
}) {
  return {
    'google': {
      'connected': googleConnected,
      'email': 'alice@gmail.com',
      'gmail_available': gmailAvailable,
      'calendar_available': calendarAvailable,
      'drive_available': driveAvailable,
    },
    'yandex_mail': {'connected': false, 'email': null},
    'yandex_calendar': {'connected': false, 'email': null},
    'mattermost': mattermost,
  };
}

Map<String, dynamic> accountSettingsJson({
  String timezone = 'Europe/Amsterdam',
  String assistantModel = 'gpt-5.6-luna',
  String assistantReasoningEffort = 'low',
  String assistantVerbosity = 'low',
  bool openaiKeyConfigured = false,
  List<String> allowedAssistantModels = const ['gpt-5.6-luna', 'gpt-5.6-terra'],
}) {
  return {
    'timezone': timezone,
    'assistant_model': assistantModel,
    'assistant_reasoning_effort': assistantReasoningEffort,
    'assistant_verbosity': assistantVerbosity,
    'openai_key_configured': openaiKeyConfigured,
    'allowed_assistant_models': allowedAssistantModels,
  };
}

bool isAccountSettingsRequest(Uri url) => url.path.endsWith('/me/settings');

class StubSecretaryApiClient extends SecretaryApiClient {
  StubSecretaryApiClient({
    required Connections connections,
    required UserSettings settings,
    http.Client? httpClient,
  })  : _connections = connections,
        _settings = settings,
        super(httpClient: httpClient ?? MockClient((_) async => http.Response('{}', 404)));

  final Connections _connections;
  final UserSettings _settings;

  @override
  Future<Connections> getConnections() async => _connections;

  @override
  Future<UserSettings> getSettings() async => _settings;
}

SecretaryApiClient buildAccountApiClient({
  Map<String, dynamic>? connectionsJson,
  Map<String, dynamic>? settingsJson,
  http.Client? httpClient,
}) {
  return StubSecretaryApiClient(
    connections: Connections.fromJson(connectionsJson ?? accountConnectionsJson()),
    settings: UserSettings.fromJson(settingsJson ?? accountSettingsJson()),
    httpClient: httpClient,
  );
}

AccountScreen buildAccountScreen({
  required SecretaryApiClient apiClient,
  required AuthController authController,
  Map<String, dynamic>? connectionsJson,
  Map<String, dynamic>? settingsJson,
}) {
  return AccountScreen(
    apiClient: apiClient,
    authController: authController,
    initialConnections: Connections.fromJson(connectionsJson ?? accountConnectionsJson()),
    initialSettings: UserSettings.fromJson(settingsJson ?? accountSettingsJson()),
  );
}

Future<void> pumpAccountReady(WidgetTester tester, Widget child) async {
  await tester.pumpWidget(MaterialApp(home: child));
  await tester.pump();
  for (var i = 0; i < 20; i++) {
    await tester.pump(const Duration(milliseconds: 50));
    if (find.textContaining('Gmail доступен').evaluate().isNotEmpty) {
      return;
    }
  }
}

Future<void> tapAccountText(WidgetTester tester, String text) async {
  final finder = find.text(text);
  await tester.ensureVisible(finder);
  await tester.pump();
  await tester.tap(finder);
}
