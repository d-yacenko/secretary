import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/auth/token_store.dart';
import 'package:personal_secretary/capture/capture_controller.dart';
import 'package:personal_secretary/capture/capture_draft.dart';

void main() {
  const baseUrl = 'https://secretary.example';
  const token = 'capture-token';

  CaptureController buildController(MockClient mock) {
    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    return CaptureController(apiClient: apiClient, authController: auth);
  }

  test('blank text cannot submit', () async {
    final controller = buildController(MockClient((request) async {
      return http.Response('{}', 201);
    }));
    controller.setText('   ');
    await controller.submit();
    expect(controller.submitState, CaptureSubmitState.validationError);
  });

  test('exact whitespace and text preserved in request', () async {
    Map<String, dynamic>? body;
    final controller = buildController(MockClient((request) async {
      body = jsonDecode(request.body) as Map<String, dynamic>;
      return http.Response(
        jsonEncode({
          'task_id': 't1',
          'context_edge_ids': [],
          'dependency_edge_ids': [],
        }),
        201,
      );
    }));
    controller.setText('  leading space');
    await controller.submit();
    expect(body!['text'], '  leading space');
  });

  test('title is optional', () async {
    Map<String, dynamic>? body;
    final controller = buildController(MockClient((request) async {
      body = jsonDecode(request.body) as Map<String, dynamic>;
      return http.Response(
        jsonEncode({
          'task_id': 't1',
          'context_edge_ids': [],
          'dependency_edge_ids': [],
        }),
        201,
      );
    }));
    controller.setText('task body');
    await controller.submit();
    expect(body!.containsKey('title'), isFalse);
  });

  test('max length validation blocks submit', () async {
    final controller = buildController(MockClient((request) async {
      return http.Response('{}', 201);
    }));
    controller.setText('x' * (CaptureDraft.maxTextLength + 1));
    expect(controller.draft.canSubmit, isFalse);

    controller.setText('ok');
    controller.setTitle('t' * (CaptureDraft.maxTitleLength + 1));
    expect(controller.draft.canSubmit, isFalse);
  });

  test('submit disabled while request pending', () async {
    final controller = buildController(MockClient((request) async {
      await Future<void>.delayed(const Duration(milliseconds: 100));
      return http.Response(
        jsonEncode({
          'task_id': 't1',
          'context_edge_ids': [],
          'dependency_edge_ids': [],
        }),
        201,
      );
    }));
    controller.setText('task');
    final first = controller.submit();
    expect(controller.submitState, CaptureSubmitState.submitting);
    await first;
  });

  test('success clears draft', () async {
    final controller = buildController(MockClient((request) async {
      return http.Response(
        jsonEncode({
          'task_id': 'task-42',
          'context_edge_ids': [],
          'dependency_edge_ids': [],
        }),
        201,
      );
    }));
    controller.setText('done task');
    await controller.submit();
    expect(controller.submitState, CaptureSubmitState.success);
    expect(controller.draft.text, isEmpty);
    expect(controller.lastResult?.taskId, 'task-42');
  });

  test('failure preserves draft', () async {
    final controller = buildController(MockClient((request) async {
      return http.Response(jsonEncode({'detail': 'validation failed'}), 422);
    }));
    controller.setText('keep me');
    await controller.submit();
    expect(controller.draft.text, 'keep me');
    expect(controller.submitState, CaptureSubmitState.validationError);
  });

  test('capture library has no OpenAI/LLM client references', () {
    final captureDir = Directory('lib/capture');
    final blocked = RegExp(r'openai|chatgpt|gpt-', caseSensitive: false);
    for (final entity in captureDir.listSync()) {
      if (entity is! File || !entity.path.endsWith('.dart')) continue;
      final content = entity.readAsStringSync();
      expect(blocked.hasMatch(content), isFalse, reason: entity.path);
    }
  });

  test('capture draft preserves exact text in API request', () {
    final draft = CaptureDraft(text: '  spaced  ');
    final json = draft.toRequest().toJson();
    expect(jsonEncode(json['text']), jsonEncode('  spaced  '));
  });
}
