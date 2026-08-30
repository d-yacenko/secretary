import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';
import 'package:personal_secretary/assistant/assistant_controller.dart';
import 'package:personal_secretary/assistant/assistant_screen.dart';
import 'package:personal_secretary/assistant/fake_voice_recorder.dart';
import 'package:personal_secretary/assistant/voice_temp_files.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/auth/token_store.dart';
import 'package:personal_secretary/capture/capture_controller.dart';
import 'package:personal_secretary/shell/app_shell.dart';

void main() {
  const baseUrl = 'https://secretary.example';
  const token = 'assistant-token';

  testWidgets('assistant send calls POST /assistant/message', (tester) async {
    int assistantCalls = 0;
    final mock = MockClient((request) async {
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
      if (request.url.path == '/assistant/message') {
        assistantCalls += 1;
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['message'], 'Hello Secretary');
        expect(body['history'], isEmpty);
        return http.Response(
          jsonEncode({
            'answer': 'Hello back',
            'references': [
              {
                'object_id': 'task-1',
                'title': 'Referenced task',
                'kind': 'task',
                'canonical_uri': null,
              },
            ],
            'affected_objects': [],
          }),
          200,
        );
      }
      if (request.url.path.startsWith('/objects/')) {
        return http.Response(
          jsonEncode({
            'id': 'task-1',
            'kind': 'task',
            'title': 'Referenced task',
            'body': null,
            'provider': null,
            'external_id': null,
            'canonical_uri': null,
            'status': null,
            'start_at': null,
            'due_at': null,
            'metadata': {},
            'origin': 'user',
            'state': 'confirmed',
            'confidence': null,
            'created_at': '2026-08-28T08:00:00Z',
            'updated_at': '2026-08-28T08:00:00Z',
          }),
          200,
        );
      }
      return http.Response('{}', 404);
    });

    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    final capture = CaptureController(apiClient: apiClient, authController: auth);
    final assistant = AssistantController(
      apiClient: apiClient,
      authController: auth,
      voiceRecorder: FakeVoiceRecorder(),
      voiceTempFiles: VoiceTempFiles(
        directory: Directory.systemTemp.createTempSync('assistant_test_voice'),
      ),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: AppShell(
          authController: auth,
          captureController: capture,
          assistantController: assistant,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Assistant'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('assistant_input')), 'Hello Secretary');
    await tester.tap(find.widgetWithText(FilledButton, 'Send'));
    await tester.pump();
    await tester.pumpAndSettle();

    expect(assistantCalls, 1);
    expect(find.text('Hello back'), findsOneWidget);
    expect(find.text('task: Referenced task'), findsOneWidget);
  });

  testWidgets('assistant sends context_object_id without copying body', (tester) async {
    Map<String, dynamic>? lastBody;
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        lastBody = jsonDecode(request.body) as Map<String, dynamic>;
        return http.Response(
          jsonEncode({
            'answer': 'Course context used',
            'references': [],
            'affected_objects': [],
          }),
          200,
        );
      }
      return http.Response('{}', 404);
    });

    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    final assistant = AssistantController(
      apiClient: apiClient,
      authController: auth,
      voiceRecorder: FakeVoiceRecorder(),
      voiceTempFiles: VoiceTempFiles(
        directory: Directory.systemTemp.createTempSync('assistant_test_voice'),
      ),
    );
    assistant.setObjectContext(
      SecretaryObject(
        id: 'obj-1',
        kind: 'course',
        title: 'Intro Course',
        body: 'Syllabus body must not be sent',
        metadata: {},
        origin: 'user',
        state: 'confirmed',
        createdAt: '2026-08-28T08:00:00Z',
        updatedAt: '2026-08-28T08:00:00Z',
      ),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: AssistantScreen(
          controller: assistant,
          apiClient: apiClient,
          authController: auth,
          captureController: CaptureController(
            apiClient: apiClient,
            authController: auth,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('Intro Course'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('assistant_input')), 'What is this?');
    await tester.tap(find.widgetWithText(FilledButton, 'Send'));
    await tester.pumpAndSettle();

    expect(lastBody?['context_object_id'], 'obj-1');
    expect(lastBody?['message'], isNot(contains('Syllabus')));
    expect(find.text('Course context used'), findsOneWidget);
  });

  testWidgets('assistant renders proposed affected objects', (tester) async {
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(
          jsonEncode({
            'answer': 'I created a proposed task to prepare the course outline.',
            'references': [],
            'affected_objects': [
              {
                'object_id': 'task-proposed-1',
                'title': 'Prepare course outline',
                'kind': 'task',
                'state': 'proposed',
              },
            ],
          }),
          200,
        );
      }
      return http.Response('{}', 404);
    });

    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    final assistant = AssistantController(
      apiClient: apiClient,
      authController: auth,
      voiceRecorder: FakeVoiceRecorder(),
      voiceTempFiles: VoiceTempFiles(
        directory: Directory.systemTemp.createTempSync('assistant_test_voice'),
      ),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: AssistantScreen(
          controller: assistant,
          apiClient: apiClient,
          authController: auth,
          captureController: CaptureController(
            apiClient: apiClient,
            authController: auth,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('assistant_input')), 'Create task');
    await tester.tap(find.widgetWithText(FilledButton, 'Send'));
    await tester.pumpAndSettle();

    expect(find.text('Affected objects:'), findsOneWidget);
    expect(find.text('task: Prepare course outline — proposed'), findsOneWidget);
  });

  testWidgets('logout clears assistant conversation and context', (tester) async {
    final apiClient = SecretaryApiClient(
      httpClient: MockClient((request) async => http.Response('{}', 404)),
    );
    apiClient.configure(baseUrl: baseUrl, token: token);
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    final assistant = AssistantController(
      apiClient: apiClient,
      authController: auth,
      voiceRecorder: FakeVoiceRecorder(),
      voiceTempFiles: VoiceTempFiles(
        directory: Directory.systemTemp.createTempSync('assistant_test_voice'),
      ),
    );
    assistant.setObjectContext(
      SecretaryObject(
        id: 'obj-1',
        kind: 'course',
        title: 'Intro Course',
        metadata: {},
        origin: 'user',
        state: 'confirmed',
        createdAt: '2026-08-28T08:00:00Z',
        updatedAt: '2026-08-28T08:00:00Z',
      ),
    );
    assistant.resetSession();
    expect(assistant.objectContext, isNull);
    expect(assistant.messages, isEmpty);
  });
}
