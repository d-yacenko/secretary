import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/api/api_error.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';
import 'package:personal_secretary/assistant/assistant_controller.dart';
import 'package:personal_secretary/assistant/fake_speech_player.dart';
import 'package:personal_secretary/assistant/fake_voice_recorder.dart';
import 'package:personal_secretary/assistant/voice_invocation_source.dart';
import 'package:personal_secretary/assistant/voice_output_policy.dart';
import 'package:personal_secretary/assistant/voice_output_policy_controller.dart';
import 'package:personal_secretary/assistant/voice_output_policy_store.dart';
import 'package:personal_secretary/assistant/voice_temp_files.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/auth/token_store.dart';

void main() {
  const baseUrl = 'https://secretary.example';
  const token = 'voice-policy-token';

  late Directory tempDir;

  setUp(() {
    tempDir = Directory.systemTemp.createTempSync('secretary_voice_policy');
  });

  tearDown(() {
    if (tempDir.existsSync()) {
      tempDir.deleteSync(recursive: true);
    }
  });

  http.Response jsonResponse(Object body, [int status = 200]) {
    return http.Response.bytes(
      utf8.encode(jsonEncode(body)),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );
  }

  http.Response speechOk() {
    return http.Response.bytes(
      [1, 2, 3, 4],
      200,
      headers: {'content-type': 'audio/mpeg'},
    );
  }

  Map<String, dynamic> pendingCommunicationPlan() {
    return {
      'answer': 'Могу отправить письмо.',
      'references': [],
      'affected_objects': [],
      'pending_action_plan': {
        'id': 'plan-email',
        'status': 'pending',
        'expires_at': '2026-09-13T12:00:00Z',
        'actions': [
          {
            'tool_name': 'send_email',
            'arguments': {
              'to': ['ivan@example.com'],
              'subject': 'Статус',
              'body': 'Пришлю завтра.',
            },
          },
        ],
      },
    };
  }

  UserMe userMe(String id) {
    return UserMe(id: id, displayName: id, createdAt: '2026-01-01T00:00:00Z');
  }

  AuthController buildAuth(SecretaryApiClient apiClient, {String? userId}) {
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    if (userId != null) {
      auth.user = userMe(userId);
    }
    return auth;
  }

  AssistantController buildAssistant({
    required SecretaryApiClient apiClient,
    required AuthController auth,
    VoiceOutputPolicy policy = VoiceOutputPolicy.handsFreeOnly,
    VoiceOutputPolicyController? voiceOutputPolicy,
    FakeVoiceRecorder? voiceRecorder,
    FakeSpeechPlayer? speechPlayer,
    bool lockScreenSession = false,
  }) {
    return AssistantController(
      apiClient: apiClient,
      authController: auth,
      voiceRecorder: voiceRecorder ?? FakeVoiceRecorder(),
      voiceTempFiles: VoiceTempFiles(directory: tempDir),
      speechPlayer: speechPlayer ?? FakeSpeechPlayer(),
      voiceOutputPolicy:
          voiceOutputPolicy ??
          VoiceOutputPolicyController(
            authController: auth,
            store: VoiceOutputPolicyStore.memory(),
            initialPolicy: policy,
          ),
      lockScreenSession: lockScreenSession,
    );
  }

  Future<void> waitUntil(bool Function() condition) async {
    final end = DateTime.now().add(const Duration(seconds: 3));
    while (!condition()) {
      if (DateTime.now().isAfter(end)) {
        fail('timed out waiting for condition');
      }
      await Future<void>.delayed(const Duration(milliseconds: 10));
    }
  }

  test('default preference is handsFreeOnly', () {
    expect(VoiceOutputPolicy.handsFreeOnly, VoiceOutputPolicy.values.first);
    final store = VoiceOutputPolicyStore.memory();
    expect(
      VoiceOutputPolicyStore.decode(null),
      VoiceOutputPolicy.handsFreeOnly,
    );
    expect(store.runtimeType, VoiceOutputPolicyStore);
  });

  test('preference is per authenticated user on this device', () async {
    final apiClient = SecretaryApiClient(
      httpClient: MockClient((_) async => http.Response('{}', 404)),
    );
    apiClient.configure(baseUrl: baseUrl, token: token);
    final auth = buildAuth(apiClient, userId: 'user-a');
    final store = VoiceOutputPolicyStore.memory();
    final policy = VoiceOutputPolicyController(
      authController: auth,
      store: store,
    );
    await policy.attach();
    expect(policy.policy, VoiceOutputPolicy.handsFreeOnly);
    await policy.setPolicy(VoiceOutputPolicy.never);

    auth.user = userMe('user-b');
    await policy.attach();
    expect(policy.policy, VoiceOutputPolicy.handsFreeOnly);
    await policy.setPolicy(VoiceOutputPolicy.allVoiceInput);

    auth.user = userMe('user-a');
    await policy.attach();
    expect(policy.policy, VoiceOutputPolicy.never);
    expect(await store.load('user-b'), VoiceOutputPolicy.allVoiceInput);
    policy.dispose();
  });

  test('typed turn never auto-speaks', () async {
    var speechCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        return jsonResponse({
          'answer': 'ok',
          'references': [],
          'affected_objects': [],
        });
      }
      if (request.url.path == '/assistant/speech') {
        speechCalls += 1;
        return speechOk();
      }
      return http.Response('{}', 404);
    });
    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final assistant = buildAssistant(
      apiClient: apiClient,
      auth: buildAuth(apiClient),
      policy: VoiceOutputPolicy.allVoiceInput,
    );
    await assistant.sendMessage('Напечатанный вопрос');
    expect(speechCalls, 0);
    expect(assistant.turnSource, VoiceInvocationSource.typed);
    expect(assistant.autoSpeechAllowed, isFalse);
    assistant.dispose();
  });

  Future<int> runVoiceTurn({
    required VoiceOutputPolicy policy,
    required VoiceInvocationSource source,
    VoiceOutputPolicyController? controller,
  }) async {
    var speechCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/transcribe') {
        return jsonResponse({'text': 'Какая свежая почта?'});
      }
      if (request.url.path == '/assistant/message') {
        return jsonResponse({
          'answer': 'Свежих писем нет.',
          'references': [],
          'affected_objects': [],
        });
      }
      if (request.url.path == '/assistant/speech') {
        speechCalls += 1;
        return speechOk();
      }
      return http.Response('{}', 404);
    });
    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final assistant = buildAssistant(
      apiClient: apiClient,
      auth: buildAuth(apiClient),
      policy: policy,
      voiceOutputPolicy: controller,
    );
    if (source == VoiceInvocationSource.screenMic) {
      await assistant.startVoiceRecording();
      await assistant.stopVoiceRecordingAndTranscribe();
    } else {
      await assistant.handleVoiceTrigger(source: source);
      await assistant.handleVoiceTrigger(
        source: VoiceInvocationSource.screenMic,
      );
      await waitUntil(() => assistant.messages.isNotEmpty);
    }
    final calls = speechCalls;
    expect(assistant.turnSource, source);
    assistant.dispose();
    return calls;
  }

  test('screen mic + default => no TTS', () async {
    expect(
      await runVoiceTurn(
        policy: VoiceOutputPolicy.handsFreeOnly,
        source: VoiceInvocationSource.screenMic,
      ),
      0,
    );
  });

  test('screen mic + allVoiceInput => TTS', () async {
    expect(
      await runVoiceTurn(
        policy: VoiceOutputPolicy.allVoiceInput,
        source: VoiceInvocationSource.screenMic,
      ),
      greaterThan(0),
    );
  });

  test('screen mic + never => no TTS', () async {
    expect(
      await runVoiceTurn(
        policy: VoiceOutputPolicy.never,
        source: VoiceInvocationSource.screenMic,
      ),
      0,
    );
  });

  test('hardware + default => TTS', () async {
    expect(
      await runVoiceTurn(
        policy: VoiceOutputPolicy.handsFreeOnly,
        source: VoiceInvocationSource.hardwareButton,
      ),
      greaterThan(0),
    );
  });

  test('system assistant + default => TTS', () async {
    expect(
      await runVoiceTurn(
        policy: VoiceOutputPolicy.handsFreeOnly,
        source: VoiceInvocationSource.systemAssistant,
      ),
      greaterThan(0),
    );
  });

  test('hardware and system + never => no TTS', () async {
    expect(
      await runVoiceTurn(
        policy: VoiceOutputPolicy.never,
        source: VoiceInvocationSource.hardwareButton,
      ),
      0,
    );
    expect(
      await runVoiceTurn(
        policy: VoiceOutputPolicy.never,
        source: VoiceInvocationSource.systemAssistant,
      ),
      0,
    );
  });

  test('source and policy are frozen at recording start', () async {
    var speechCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/transcribe') {
        return jsonResponse({'text': 'Какая свежая почта?'});
      }
      if (request.url.path == '/assistant/message') {
        return jsonResponse({
          'answer': 'Свежих писем нет.',
          'references': [],
          'affected_objects': [],
        });
      }
      if (request.url.path == '/assistant/speech') {
        speechCalls += 1;
        return speechOk();
      }
      return http.Response('{}', 404);
    });
    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final auth = buildAuth(apiClient);
    final policy = VoiceOutputPolicyController(
      authController: auth,
      store: VoiceOutputPolicyStore.memory(),
    );
    final assistant = buildAssistant(
      apiClient: apiClient,
      auth: auth,
      voiceOutputPolicy: policy,
    );
    await assistant.startVoiceRecording();
    expect(assistant.turnSource, VoiceInvocationSource.screenMic);
    expect(assistant.autoSpeechAllowed, isFalse);
    await policy.setPolicy(VoiceOutputPolicy.allVoiceInput);
    await assistant.stopVoiceRecordingAndTranscribe();
    expect(assistant.autoSpeechAllowed, isFalse);
    expect(speechCalls, 0);
    assistant.dispose();
  });

  test('hardware stop does not promote a screenMic turn', () async {
    var speechCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/transcribe') {
        return jsonResponse({'text': 'Какая свежая почта?'});
      }
      if (request.url.path == '/assistant/message') {
        return jsonResponse({
          'answer': 'Свежих писем нет.',
          'references': [],
          'affected_objects': [],
        });
      }
      if (request.url.path == '/assistant/speech') {
        speechCalls += 1;
        return speechOk();
      }
      return http.Response('{}', 404);
    });
    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final assistant = buildAssistant(
      apiClient: apiClient,
      auth: buildAuth(apiClient),
    );
    await assistant.startVoiceRecording();
    await assistant.handleVoiceTrigger(
      source: VoiceInvocationSource.hardwareButton,
    );
    expect(assistant.turnSource, VoiceInvocationSource.screenMic);
    expect(assistant.autoSpeechAllowed, isFalse);
    expect(speechCalls, 0);
    assistant.dispose();
  });

  test('UI stop of a hardware-started turn remains hands-free', () async {
    var speechCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/transcribe') {
        return jsonResponse({'text': 'Какая свежая почта?'});
      }
      if (request.url.path == '/assistant/message') {
        return jsonResponse({
          'answer': 'Свежих писем нет.',
          'references': [],
          'affected_objects': [],
        });
      }
      if (request.url.path == '/assistant/speech') {
        speechCalls += 1;
        return speechOk();
      }
      return http.Response('{}', 404);
    });
    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final assistant = buildAssistant(
      apiClient: apiClient,
      auth: buildAuth(apiClient),
    );
    await assistant.handleVoiceTrigger(
      source: VoiceInvocationSource.hardwareButton,
    );
    await assistant.handleVoiceTrigger(source: VoiceInvocationSource.screenMic);
    expect(assistant.turnSource, VoiceInvocationSource.hardwareButton);
    expect(assistant.autoSpeechAllowed, isTrue);
    expect(speechCalls, greaterThan(0));
    assistant.dispose();
  });

  test('non-speaking Pending Action Plan does not arm voice Да', () async {
    var transcripts = <String>['Ответь Иванову', 'Да'];
    var approveCalls = 0;
    var speechCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/transcribe') {
        final text = transcripts.isEmpty ? 'Да' : transcripts.removeAt(0);
        return jsonResponse({'text': text});
      }
      if (request.url.path == '/assistant/message') {
        return jsonResponse(pendingCommunicationPlan());
      }
      if (request.url.path.contains('/approve')) {
        approveCalls += 1;
        return http.Response('{}', 500);
      }
      if (request.url.path == '/assistant/speech') {
        speechCalls += 1;
        return speechOk();
      }
      return http.Response('{}', 404);
    });
    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final assistant = buildAssistant(
      apiClient: apiClient,
      auth: buildAuth(apiClient),
    );
    await assistant.startVoiceRecording();
    await assistant.stopVoiceRecordingAndTranscribe();
    expect(assistant.hasPendingActionPlan, isTrue);
    expect(speechCalls, 0);
    await assistant.startVoiceRecording();
    await assistant.stopVoiceRecordingAndTranscribe();
    expect(approveCalls, 0);
    expect(assistant.hasPendingActionPlan, isTrue);
    assistant.dispose();
  });

  test('non-speaking exact Нет still rejects', () async {
    var transcripts = <String>['Ответь Иванову', 'Нет'];
    var approveCalls = 0;
    var rejectCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/transcribe') {
        final text = transcripts.isEmpty ? 'Нет' : transcripts.removeAt(0);
        return jsonResponse({'text': text});
      }
      if (request.url.path == '/assistant/message') {
        return jsonResponse(pendingCommunicationPlan());
      }
      if (request.url.path.contains('/approve')) {
        approveCalls += 1;
        return http.Response('{}', 500);
      }
      if (request.url.path.contains('/reject')) {
        rejectCalls += 1;
        return jsonResponse({
          'id': 'plan-email',
          'status': 'rejected',
          'expires_at': '2026-09-13T12:00:00Z',
          'actions': [],
        });
      }
      if (request.url.path == '/assistant/speech') {
        return speechOk();
      }
      return http.Response('{}', 404);
    });
    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final assistant = buildAssistant(
      apiClient: apiClient,
      auth: buildAuth(apiClient),
    );
    await assistant.startVoiceRecording();
    await assistant.stopVoiceRecordingAndTranscribe();
    await assistant.startVoiceRecording();
    await assistant.stopVoiceRecordingAndTranscribe();
    expect(approveCalls, 0);
    expect(rejectCalls, 1);
    assistant.dispose();
  });

  test('hands-free preview arms Да only after complete playback', () async {
    var transcripts = <String>['Ответь Иванову', 'Да'];
    var approveCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/transcribe') {
        final text = transcripts.isEmpty ? 'Да' : transcripts.removeAt(0);
        return jsonResponse({'text': text});
      }
      if (request.url.path == '/assistant/message') {
        return jsonResponse(pendingCommunicationPlan());
      }
      if (request.url.path.contains('/approve')) {
        approveCalls += 1;
        return jsonResponse({
          'id': 'plan-email',
          'status': 'executed',
          'expires_at': '2026-09-13T12:00:00Z',
          'actions': [],
        });
      }
      if (request.url.path.contains('/resume')) {
        return jsonResponse({
          'answer': 'Письмо отправлено.',
          'affected_objects': [],
        });
      }
      if (request.url.path == '/assistant/speech') {
        return speechOk();
      }
      return http.Response('{}', 404);
    });
    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final assistant = buildAssistant(
      apiClient: apiClient,
      auth: buildAuth(apiClient),
    );
    await assistant.handleVoiceTrigger(
      source: VoiceInvocationSource.hardwareButton,
    );
    await assistant.handleVoiceTrigger(
      source: VoiceInvocationSource.hardwareButton,
    );
    expect(assistant.hasPendingActionPlan, isTrue);
    await assistant.handleVoiceTrigger(
      source: VoiceInvocationSource.hardwareButton,
    );
    await assistant.handleVoiceTrigger(
      source: VoiceInvocationSource.hardwareButton,
    );
    expect(approveCalls, 1);
    assistant.dispose();
  });

  test('interrupted preview leaves affirmative unarmed', () async {
    var transcripts = <String>['Ответь Иванову', 'Да'];
    var approveCalls = 0;
    final speechPlayer = FakeSpeechPlayer(completeImmediately: false);
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/transcribe') {
        final text = transcripts.isEmpty ? 'Да' : transcripts.removeAt(0);
        return jsonResponse({'text': text});
      }
      if (request.url.path == '/assistant/message') {
        return jsonResponse(pendingCommunicationPlan());
      }
      if (request.url.path.contains('/approve')) {
        approveCalls += 1;
        return http.Response('{}', 500);
      }
      if (request.url.path == '/assistant/speech') {
        return speechOk();
      }
      return http.Response('{}', 404);
    });
    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final assistant = buildAssistant(
      apiClient: apiClient,
      auth: buildAuth(apiClient),
      speechPlayer: speechPlayer,
    );
    final first = () async {
      await assistant.handleVoiceTrigger(
        source: VoiceInvocationSource.hardwareButton,
      );
      await assistant.handleVoiceTrigger(
        source: VoiceInvocationSource.hardwareButton,
      );
    }();
    await waitUntil(() => assistant.voiceState == AssistantVoiceState.speaking);
    await assistant.handleVoiceTrigger(
      source: VoiceInvocationSource.hardwareButton,
    );
    speechPlayer.completeImmediately = true;
    await assistant.handleVoiceTrigger(
      source: VoiceInvocationSource.hardwareButton,
    );
    expect(approveCalls, 0);
    expect(assistant.hasPendingActionPlan, isTrue);
    await first;
    assistant.dispose();
  });

  test('locked external write remains blocked', () async {
    var approveCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/transcribe') {
        return jsonResponse({'text': 'Ответь Иванову'});
      }
      if (request.url.path == '/assistant/message') {
        return jsonResponse(pendingCommunicationPlan());
      }
      if (request.url.path.contains('/approve')) {
        approveCalls += 1;
        return http.Response('{}', 500);
      }
      if (request.url.path == '/assistant/speech') {
        return speechOk();
      }
      return http.Response('{}', 404);
    });
    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final assistant = buildAssistant(
      apiClient: apiClient,
      auth: buildAuth(apiClient),
      lockScreenSession: true,
    );
    assistant.keyguardLocked = true;
    assistant.lockScreenVoiceEnabled = true;
    await assistant.handleVoiceTrigger(
      source: VoiceInvocationSource.systemAssistant,
    );
    await assistant.handleVoiceTrigger(
      source: VoiceInvocationSource.systemAssistant,
    );
    await waitUntil(() => assistant.hasPendingActionPlan);
    final pendingIndex = assistant.messages.lastIndexWhere(
      (message) => message.actionPlan?.cardState == ActionPlanCardState.pending,
    );
    await assistant.approveActionPlanAt(pendingIndex);
    expect(approveCalls, 0);
    expect(assistant.blocksExternalWrite, isTrue);
    assistant.dispose();
  });

  test('matrix matches VoiceOutputPolicy.allowsAutoSpeech', () {
    const policies = VoiceOutputPolicy.values;
    const sources = VoiceInvocationSource.values;
    for (final policy in policies) {
      for (final source in sources) {
        final allowed = policy.allowsAutoSpeech(source);
        if (policy == VoiceOutputPolicy.never ||
            source == VoiceInvocationSource.typed) {
          expect(allowed, isFalse, reason: '$policy $source');
        } else if (policy == VoiceOutputPolicy.allVoiceInput) {
          expect(allowed, source.isVoiceInput, reason: '$policy $source');
        } else {
          expect(allowed, source.isHandsFree, reason: '$policy $source');
        }
      }
    }
  });

  test('legacy transcription unavailable copy maps locally', () {
    expect(
      localTranscriptionMessage(
        ServerException('Transcription provider unavailable'),
      ),
      transcriptionProviderFailedMessage,
    );
    expect(
      localTranscriptionMessage(
        ValidationException('ignored', code: transcriptionAudioInvalidCode),
      ),
      transcriptionAudioInvalidMessage,
    );
  });
}
