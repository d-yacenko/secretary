import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/auth/token_store.dart';
import 'package:personal_secretary/assistant/assistant_controller.dart';
import 'package:personal_secretary/local/local_intake_actions.dart';
import 'package:shared_preferences/shared_preferences.dart';

http.Response _jsonResponse(Object body, {int statusCode = 200}) {
  return http.Response.bytes(
    utf8.encode(jsonEncode(body)),
    statusCode,
    headers: {'content-type': 'application/json; charset=utf-8'},
  );
}

Map<String, dynamic> _objectJson({
  required String id,
  required String title,
}) {
  return {
    'id': id,
    'kind': 'file',
    'title': title,
    'body': null,
    'provider': 'local_device',
    'external_id': null,
    'canonical_uri': null,
    'status': null,
    'start_at': null,
    'due_at': null,
    'metadata': {},
    'origin': 'user',
    'state': 'confirmed',
    'confidence': null,
    'created_at': '2026-01-01T00:00:00Z',
    'updated_at': '2026-01-01T00:00:00Z',
  };
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Directory tempDir;

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    tempDir = Directory.systemTemp.createTempSync('intake-actions-test-');
  });

  tearDown(() {
    if (tempDir.existsSync()) {
      tempDir.deleteSync(recursive: true);
    }
  });

  testWidgets('multiple dropped files prompt active context choice', (tester) async {
    final fileA = File('${tempDir.path}/a.txt');
    final fileB = File('${tempDir.path}/b.txt');
    fileA.writeAsStringSync('alpha');
    fileB.writeAsStringSync('beta');

    int intakeCount = 0;
    int assistantPosts = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/assistant/message') {
        assistantPosts += 1;
      }
      if (request.url.path == '/local/devices/register') {
        return _jsonResponse({
          'device_id': 'device-1',
          'device_key': 'device-key-1',
          'display_name': 'Test device',
          'created': true,
        }, statusCode: 201);
      }
      if (request.url.path == '/local/files/client-intake') {
        intakeCount += 1;
        final objectId = intakeCount == 1 ? 'obj-a' : 'obj-b';
        return _jsonResponse({
          'object_id': objectId,
          'status': 'created',
          'jobs_enqueued': 0,
          'representations_created': 1,
          'metadata_only': false,
        }, statusCode: 201);
      }
      if (request.url.path == '/objects/obj-a') {
        return _jsonResponse(_objectJson(id: 'obj-a', title: 'a.txt'));
      }
      if (request.url.path == '/objects/obj-b') {
        return _jsonResponse(_objectJson(id: 'obj-b', title: 'b.txt'));
      }
      return http.Response('{}', 404);
    });

    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: 'https://example.com', token: 'token');
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    final assistant = AssistantController(apiClient: apiClient, authController: auth);
    final actions = LocalIntakeActions(
      apiClient: apiClient,
      authController: auth,
      assistantController: assistant,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: ElevatedButton(
              onPressed: () => actions.registerDroppedFiles(
                context,
                [fileA.path, fileB.path],
              ),
              child: const Text('drop'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('drop'));
    await tester.pumpAndSettle();

    expect(find.text('Выберите активный контекст'), findsOneWidget);
    expect(find.text('a.txt'), findsOneWidget);
    expect(find.text('b.txt'), findsOneWidget);

    await tester.tap(find.text('b.txt'));
    await tester.pumpAndSettle();

    expect(assistant.objectContext?.id, 'obj-b');
    expect(assistant.objectContext?.title, 'b.txt');
    expect(intakeCount, 2);
    expect(assistantPosts, 0);
    expect(find.textContaining('Добавлено файлов: 2'), findsOneWidget);
    expect(find.textContaining('Активный контекст: b.txt'), findsOneWidget);
  });

  testWidgets('non-inbox local intake does not send explicit intake mode', (tester) async {
    final file = File('${tempDir.path}/plain.txt');
    file.writeAsStringSync('plain');

    String? intakeBody;
    final mock = MockClient((request) async {
      if (request.url.path == '/local/devices/register') {
        return _jsonResponse({
          'device_id': 'device-1',
          'device_key': 'device-key-1',
          'display_name': 'Test device',
          'created': true,
        }, statusCode: 201);
      }
      if (request.url.path == '/local/files/client-intake') {
        intakeBody = request.body;
        return _jsonResponse({
          'object_id': 'obj-plain',
          'status': 'created',
          'jobs_enqueued': 0,
          'representations_created': 1,
          'metadata_only': false,
        }, statusCode: 201);
      }
      if (request.url.path == '/objects/obj-plain') {
        return _jsonResponse(_objectJson(id: 'obj-plain', title: 'plain.txt'));
      }
      return http.Response('{}', 404);
    });

    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: 'https://example.com', token: 'token');
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    final actions = LocalIntakeActions(
      apiClient: apiClient,
      authController: auth,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: ElevatedButton(
              onPressed: () => actions.registerDroppedFiles(context, [file.path]),
              child: const Text('drop'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('drop'));
    await tester.pumpAndSettle();

    final decoded = jsonDecode(intakeBody!) as Map<String, dynamic>;
    expect(decoded.containsKey('intake_mode'), isFalse);
  });

  testWidgets('inbox local intake sends explicit intake mode', (tester) async {
    final file = File('${tempDir.path}/inbox.txt');
    file.writeAsStringSync('inbox');

    String? intakeBody;
    final mock = MockClient((request) async {
      if (request.url.path == '/local/devices/register') {
        return _jsonResponse({
          'device_id': 'device-1',
          'device_key': 'device-key-1',
          'display_name': 'Test device',
          'created': true,
        }, statusCode: 201);
      }
      if (request.url.path == '/local/files/client-intake') {
        intakeBody = request.body;
        return _jsonResponse({
          'object_id': 'obj-inbox',
          'status': 'created',
          'jobs_enqueued': 0,
          'representations_created': 1,
          'metadata_only': false,
        }, statusCode: 201);
      }
      if (request.url.path == '/objects/obj-inbox') {
        return _jsonResponse(_objectJson(id: 'obj-inbox', title: 'inbox.txt'));
      }
      return http.Response('{}', 404);
    });

    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: 'https://example.com', token: 'token');
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    final actions = LocalIntakeActions(
      apiClient: apiClient,
      authController: auth,
      forInbox: true,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: ElevatedButton(
              onPressed: () => actions.registerDroppedFiles(context, [file.path]),
              child: const Text('drop'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('drop'));
    await tester.pumpAndSettle();

    final decoded = jsonDecode(intakeBody!) as Map<String, dynamic>;
    expect(decoded['intake_mode'], 'explicit_local');
  });

  testWidgets('failed local intake does not invoke success callback', (tester) async {
    final file = File('${tempDir.path}/fail.txt');
    file.writeAsStringSync('fail');

    int successCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/local/devices/register') {
        return _jsonResponse({
          'device_id': 'device-1',
          'device_key': 'device-key-1',
          'display_name': 'Test device',
          'created': true,
        }, statusCode: 201);
      }
      if (request.url.path == '/local/files/client-intake') {
        return _jsonResponse({'detail': 'intake failed'}, statusCode: 400);
      }
      return http.Response('{}', 404);
    });

    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: 'https://example.com', token: 'token');
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    final actions = LocalIntakeActions(
      apiClient: apiClient,
      authController: auth,
      forInbox: true,
      onIntakeSuccess: () => successCalls++,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: ElevatedButton(
              onPressed: () => actions.registerDroppedFiles(context, [file.path]),
              child: const Text('drop'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('drop'));
    await tester.pumpAndSettle();

    expect(successCalls, 0);
  });

  testWidgets('mixed local drop with partial success invokes one success callback', (tester) async {
    final okFile = File('${tempDir.path}/ok.txt');
    final badFile = File('${tempDir.path}/bad.txt');
    okFile.writeAsStringSync('ok');
    badFile.writeAsStringSync('bad');

    int successCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/local/devices/register') {
        return _jsonResponse({
          'device_id': 'device-1',
          'device_key': 'device-key-1',
          'display_name': 'Test device',
          'created': true,
        }, statusCode: 201);
      }
      if (request.url.path == '/local/files/client-intake') {
        final body = jsonDecode(request.body!) as Map<String, dynamic>;
        if (body['source_path'] == badFile.path) {
          return _jsonResponse({'detail': 'intake failed'}, statusCode: 400);
        }
        return _jsonResponse({
          'object_id': 'obj-ok',
          'status': 'created',
          'jobs_enqueued': 0,
          'representations_created': 1,
          'metadata_only': false,
        }, statusCode: 201);
      }
      if (request.url.path == '/objects/obj-ok') {
        return _jsonResponse(_objectJson(id: 'obj-ok', title: 'ok.txt'));
      }
      return http.Response('{}', 404);
    });

    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: 'https://example.com', token: 'token');
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    final actions = LocalIntakeActions(
      apiClient: apiClient,
      authController: auth,
      forInbox: true,
      onIntakeSuccess: () => successCalls++,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: ElevatedButton(
              onPressed: () => actions.registerDroppedFiles(
                context,
                [okFile.path, badFile.path],
              ),
              child: const Text('drop'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('drop'));
    await tester.pumpAndSettle();

    expect(successCalls, 1);
  });
}
