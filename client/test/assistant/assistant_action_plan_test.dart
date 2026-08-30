import 'dart:convert';

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
import 'package:personal_secretary/auth/token_store.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/capture/capture_controller.dart';

void main() {
  const baseUrl = 'https://secretary.example';
  const token = 'action-plan-token';

  Map<String, dynamic> pendingPlanBody({
    String planId = 'plan-1',
    String title = 'Review the letter',
  }) {
    return {
      'answer': 'I can create a task.',
      'references': [],
      'affected_objects': [],
      'pending_action_plan': {
        'id': planId,
        'status': 'pending',
        'expires_at': '2026-08-30T12:00:00Z',
        'actions': [
          {
            'tool_name': 'create_task',
            'arguments': {'title': title, 'confidence': 0.8},
          },
        ],
      },
    };
  }

  Future<void> pumpAssistant(
    WidgetTester tester,
    AssistantController assistant,
    AuthController auth,
    CaptureController capture,
    SecretaryApiClient apiClient,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: AssistantScreen(
          controller: assistant,
          apiClient: apiClient,
          authController: auth,
          captureController: capture,
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  test('AssistantMessageResponse parses pending_action_plan', () {
    final response = AssistantMessageResponse.fromJson(pendingPlanBody());
    expect(response.pendingActionPlan?.id, 'plan-1');
    expect(response.pendingActionPlan?.actions.first.toolName, 'create_task');
  });

  test('normal response with no pending plan still parses', () {
    final response = AssistantMessageResponse.fromJson({
      'answer': 'Hello',
      'references': [],
      'affected_objects': [],
    });
    expect(response.pendingActionPlan, isNull);
  });

  testWidgets('proposal message renders Approve and Reject', (tester) async {
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(jsonEncode(pendingPlanBody()), 200);
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
      voiceTempFiles: VoiceTempFiles(),
    );

    await pumpAssistant(tester, assistant, auth, capture, apiClient);
    await assistant.sendMessage('Create a task');
    await tester.pumpAndSettle();

    expect(find.text('Требует подтверждения'), findsOneWidget);
    expect(find.text('Подтвердить'), findsOneWidget);
    expect(find.text('Отклонить'), findsOneWidget);
    expect(find.text('Create task: Review the letter'), findsOneWidget);
  });

  testWidgets('normal Send disabled while plan pending', (tester) async {
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(jsonEncode(pendingPlanBody()), 200);
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
      voiceTempFiles: VoiceTempFiles(),
    );

    await pumpAssistant(tester, assistant, auth, capture, apiClient);
    await assistant.sendMessage('Create a task');
    await tester.pumpAndSettle();

    final sendButton = tester.widget<FilledButton>(
      find.byKey(const Key('assistant_send_button')),
    );
    expect(sendButton.onPressed, isNull);
  });

  testWidgets('voice start disabled while plan pending', (tester) async {
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(jsonEncode(pendingPlanBody()), 200);
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
      voiceTempFiles: VoiceTempFiles(),
    );

    await pumpAssistant(tester, assistant, auth, capture, apiClient);
    await assistant.sendMessage('Create a task');
    await tester.pumpAndSettle();

    final voiceButton = tester.widget<IconButton>(
      find.byKey(const Key('assistant_voice_button')),
    );
    expect(voiceButton.onPressed, isNull);
  });

  testWidgets('approve sends plan ID without replacement args', (tester) async {
    String? approvePath;
    Map<String, dynamic>? approveBody;
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(jsonEncode(pendingPlanBody()), 200);
      }
      if (request.url.path == '/assistant/action-plans/plan-1/approve') {
        approvePath = request.url.path;
        approveBody = request.body.isEmpty
            ? null
            : jsonDecode(request.body) as Map<String, dynamic>;
        return http.Response(
          jsonEncode({
            'id': 'plan-1',
            'status': 'executed',
            'expires_at': '2026-08-30T12:00:00Z',
            'actions': [
              {
                'tool_name': 'create_task',
                'arguments': {'title': 'Review the letter', 'confidence': 0.8},
              },
            ],
            'result': {'actions': []},
          }),
          200,
        );
      }
      if (request.url.path == '/assistant/action-plans/plan-1/resume') {
        return http.Response(
          jsonEncode({
            'answer': 'Done.',
            'affected_objects': [
              {
                'object_id': 'task-1',
                'title': 'Review the letter',
                'kind': 'task',
                'state': 'confirmed',
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
    final capture = CaptureController(apiClient: apiClient, authController: auth);
    final assistant = AssistantController(
      apiClient: apiClient,
      authController: auth,
      voiceRecorder: FakeVoiceRecorder(),
      voiceTempFiles: VoiceTempFiles(),
    );

    await pumpAssistant(tester, assistant, auth, capture, apiClient);
    await assistant.sendMessage('Create a task');
    await tester.pumpAndSettle();

    await tester.tap(find.text('Подтвердить'));
    await tester.pump();
    await tester.pumpAndSettle();

    expect(approvePath, endsWith('/assistant/action-plans/plan-1/approve'));
    expect(approveBody, isNull);
  });

  testWidgets('executed approve triggers resume and appends final message',
      (tester) async {
    int resumeCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(jsonEncode(pendingPlanBody()), 200);
      }
      if (request.url.path == '/assistant/action-plans/plan-1/approve') {
        return http.Response(
          jsonEncode({
            'id': 'plan-1',
            'status': 'executed',
            'expires_at': '2026-08-30T12:00:00Z',
            'actions': [],
          }),
          200,
        );
      }
      if (request.url.path == '/assistant/action-plans/plan-1/resume') {
        resumeCalls += 1;
        return http.Response(
          jsonEncode({
            'answer': 'Done. I created the task.',
            'affected_objects': [
              {
                'object_id': 'task-1',
                'title': 'Review the letter',
                'kind': 'task',
                'state': 'confirmed',
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
    final capture = CaptureController(apiClient: apiClient, authController: auth);
    final assistant = AssistantController(
      apiClient: apiClient,
      authController: auth,
      voiceRecorder: FakeVoiceRecorder(),
      voiceTempFiles: VoiceTempFiles(),
    );

    await pumpAssistant(tester, assistant, auth, capture, apiClient);
    await assistant.sendMessage('Create a task');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Подтвердить'));
    await tester.pump();
    await tester.pumpAndSettle();

    expect(resumeCalls, 1);
    expect(find.text('Done. I created the task.'), findsOneWidget);
    expect(find.text('Затронутые объекты:'), findsOneWidget);
    expect(find.text('Задача: Review the letter — Открыта'), findsOneWidget);
  });

  testWidgets('reject changes card to Rejected without resume', (tester) async {
    int resumeCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(jsonEncode(pendingPlanBody()), 200);
      }
      if (request.url.path == '/assistant/action-plans/plan-1/reject') {
        return http.Response(
          jsonEncode({
            'id': 'plan-1',
            'status': 'rejected',
            'expires_at': '2026-08-30T12:00:00Z',
            'actions': [],
          }),
          200,
        );
      }
      if (request.url.path.contains('/resume')) {
        resumeCalls += 1;
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
      voiceTempFiles: VoiceTempFiles(),
    );

    await pumpAssistant(tester, assistant, auth, capture, apiClient);
    await assistant.sendMessage('Create a task');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Отклонить'));
    await tester.pumpAndSettle();

    expect(find.text('Отклонено'), findsOneWidget);
    expect(resumeCalls, 0);
    expect(assistant.hasPendingActionPlan, isFalse);
  });

  testWidgets('failed approve shows terminal failure state', (tester) async {
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(jsonEncode(pendingPlanBody()), 200);
      }
      if (request.url.path == '/assistant/action-plans/plan-1/approve') {
        return http.Response(
          jsonEncode({
            'id': 'plan-1',
            'status': 'failed',
            'expires_at': '2026-08-30T12:00:00Z',
            'actions': [],
            'failure': 'execution failed',
          }),
          409,
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
      voiceTempFiles: VoiceTempFiles(),
    );

    await pumpAssistant(tester, assistant, auth, capture, apiClient);
    await assistant.sendMessage('Create a task');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Подтвердить'));
    await tester.pumpAndSettle();

    expect(find.text('Ошибка'), findsOneWidget);
    expect(find.text('Подтвердить'), findsNothing);
  });

  testWidgets('resetSession clears plan operation state', (tester) async {
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(jsonEncode(pendingPlanBody()), 200);
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
      voiceTempFiles: VoiceTempFiles(),
    );

    await pumpAssistant(tester, assistant, auth, capture, apiClient);
    await assistant.sendMessage('Create a task');
    await tester.pumpAndSettle();
    assistant.resetSession();
    await tester.pumpAndSettle();

    expect(assistant.hasPendingActionPlan, isFalse);
    expect(
      assistant.actionPlanOperationState,
      AssistantActionPlanOperationState.idle,
    );
  });

  test('ActionPlanResponse.tryParse rejects generic conflict detail', () {
    final parsed = ActionPlanResponse.tryParse({
      'detail': 'action plan was rejected',
    });
    expect(parsed, isNull);
  });

  test('ActionPlanResponse.tryParse accepts structured failed response', () {
    final parsed = ActionPlanResponse.tryParse({
      'id': 'plan-1',
      'status': 'failed',
      'expires_at': '2026-08-30T12:00:00Z',
      'actions': [],
      'failure': 'execution failed',
    });
    expect(parsed?.status, 'failed');
  });

  testWidgets('approve network failure leaves card pending and retryable',
      (tester) async {
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(jsonEncode(pendingPlanBody()), 200);
      }
      if (request.url.path.contains('/approve')) {
        throw http.ClientException('Connection failed');
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
      voiceTempFiles: VoiceTempFiles(),
    );

    await pumpAssistant(tester, assistant, auth, capture, apiClient);
    await assistant.sendMessage('Create a task');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Подтвердить'));
    await tester.pumpAndSettle();

    expect(assistant.messages.last.actionPlan?.cardState, ActionPlanCardState.pending);
    expect(assistant.actionPlanOperationState, AssistantActionPlanOperationState.idle);
    expect(assistant.actionPlanErrorMessage, isNotNull);
    expect(find.text('Подтвердить'), findsOneWidget);
  });

  testWidgets('reject network failure leaves card pending and retryable',
      (tester) async {
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(jsonEncode(pendingPlanBody()), 200);
      }
      if (request.url.path.contains('/reject')) {
        throw http.ClientException('Connection failed');
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
      voiceTempFiles: VoiceTempFiles(),
    );

    await pumpAssistant(tester, assistant, auth, capture, apiClient);
    await assistant.sendMessage('Create a task');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Отклонить'));
    await tester.pumpAndSettle();

    expect(assistant.messages.last.actionPlan?.cardState, ActionPlanCardState.pending);
    expect(assistant.actionPlanOperationState, AssistantActionPlanOperationState.idle);
    expect(assistant.actionPlanErrorMessage, isNotNull);
    expect(find.text('Отклонить'), findsOneWidget);
  });

  testWidgets('generic 409 detail on approve does not crash controller',
      (tester) async {
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(jsonEncode(pendingPlanBody()), 200);
      }
      if (request.url.path.contains('/approve')) {
        return http.Response(
          jsonEncode({'detail': 'action plan was rejected'}),
          409,
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
      voiceTempFiles: VoiceTempFiles(),
    );

    await pumpAssistant(tester, assistant, auth, capture, apiClient);
    await assistant.sendMessage('Create a task');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Подтвердить'));
    await tester.pumpAndSettle();

    expect(assistant.messages.last.actionPlan?.cardState, ActionPlanCardState.pending);
    expect(assistant.actionPlanOperationState, AssistantActionPlanOperationState.idle);
    expect(find.text('Подтвердить'), findsOneWidget);
  });

  testWidgets('retry approve after transient failure makes second request',
      (tester) async {
    int approveCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(jsonEncode(pendingPlanBody()), 200);
      }
      if (request.url.path.contains('/approve')) {
        approveCalls += 1;
        if (approveCalls == 1) {
          throw http.ClientException('Connection failed');
        }
        return http.Response(
          jsonEncode({
            'id': 'plan-1',
            'status': 'executed',
            'expires_at': '2026-08-30T12:00:00Z',
            'actions': [],
          }),
          200,
        );
      }
      if (request.url.path.contains('/resume')) {
        return http.Response(
          jsonEncode({
            'answer': 'Done.',
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
    final capture = CaptureController(apiClient: apiClient, authController: auth);
    final assistant = AssistantController(
      apiClient: apiClient,
      authController: auth,
      voiceRecorder: FakeVoiceRecorder(),
      voiceTempFiles: VoiceTempFiles(),
    );

    await pumpAssistant(tester, assistant, auth, capture, apiClient);
    await assistant.sendMessage('Create a task');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Подтвердить'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Подтвердить'));
    await tester.pumpAndSettle();

    expect(approveCalls, 2);
  });

  testWidgets('approve malformed 409 body leaves card pending and retryable',
      (tester) async {
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(jsonEncode(pendingPlanBody()), 200);
      }
      if (request.url.path.contains('/approve')) {
        return http.Response('not-json{{{', 409);
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
      voiceTempFiles: VoiceTempFiles(),
    );

    await pumpAssistant(tester, assistant, auth, capture, apiClient);
    await assistant.sendMessage('Create a task');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Подтвердить'));
    await tester.pumpAndSettle();

    expect(assistant.messages.last.actionPlan?.cardState, ActionPlanCardState.pending);
    expect(assistant.actionPlanOperationState, AssistantActionPlanOperationState.idle);
    expect(assistant.actionPlanErrorMessage, isNotNull);
    expect(find.text('Подтвердить'), findsOneWidget);
  });

  testWidgets('reject malformed 200 body leaves card pending and retryable',
      (tester) async {
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(jsonEncode(pendingPlanBody()), 200);
      }
      if (request.url.path.contains('/reject')) {
        return http.Response('not-json{{{', 200);
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
      voiceTempFiles: VoiceTempFiles(),
    );

    await pumpAssistant(tester, assistant, auth, capture, apiClient);
    await assistant.sendMessage('Create a task');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Отклонить'));
    await tester.pumpAndSettle();

    expect(assistant.messages.last.actionPlan?.cardState, ActionPlanCardState.pending);
    expect(assistant.actionPlanOperationState, AssistantActionPlanOperationState.idle);
    expect(assistant.actionPlanErrorMessage, isNotNull);
    expect(find.text('Отклонить'), findsOneWidget);
  });

  testWidgets('generic 409 detail on reject does not crash controller',
      (tester) async {
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return http.Response(jsonEncode(pendingPlanBody()), 200);
      }
      if (request.url.path.contains('/reject')) {
        return http.Response(
          jsonEncode({'detail': 'action plan already executed'}),
          409,
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
      voiceTempFiles: VoiceTempFiles(),
    );

    await pumpAssistant(tester, assistant, auth, capture, apiClient);
    await assistant.sendMessage('Create a task');
    await tester.pumpAndSettle();
    await tester.tap(find.text('Отклонить'));
    await tester.pumpAndSettle();

    expect(assistant.messages.last.actionPlan?.cardState, ActionPlanCardState.pending);
    expect(assistant.actionPlanOperationState, AssistantActionPlanOperationState.idle);
    expect(find.text('Отклонить'), findsOneWidget);
  });
}
