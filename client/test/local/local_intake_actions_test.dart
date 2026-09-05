import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/api/api_error.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/auth/token_store.dart';
import 'package:personal_secretary/assistant/assistant_controller.dart';
import 'package:personal_secretary/local/local_file_intake_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../test_secretary_api_client.dart';

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
  late Directory tempDir;

  setUp(() {
    SharedPreferences.setMockInitialValues({
      'secretary_device_key': 'device-key-1',
      'secretary_device_display_name': 'Test device',
    });
    tempDir = Directory.systemTemp.createTempSync('intake-actions-test-');
  });

  tearDown(() {
    if (tempDir.existsSync()) {
      tempDir.deleteSync(recursive: true);
    }
  });

  test('registerFileAndFetch loads object for multi-file intake flow', () async {
    final fileA = File('${tempDir.path}/a.txt');
    final fileB = File('${tempDir.path}/b.txt');
    fileA.writeAsStringSync('alpha');
    fileB.writeAsStringSync('beta');

    var intakeCount = 0;
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

    final apiClient = testSecretaryApiClient(mock);
    apiClient.configure(baseUrl: 'https://example.com', token: 'token');
    final service = LocalFileIntakeService(apiClient: apiClient);
    final objectA = await service.registerFileAndFetch(fileA);
    final objectB = await service.registerFileAndFetch(fileB);

    expect(objectA.title, 'a.txt');
    expect(objectB.title, 'b.txt');
    expect(intakeCount, 2);
  });

  test('non-inbox local intake does not send explicit intake mode', () async {
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
      return http.Response('{}', 404);
    });

    final apiClient = testSecretaryApiClient(mock);
    apiClient.configure(baseUrl: 'https://example.com', token: 'token');
    final service = LocalFileIntakeService(apiClient: apiClient);
    await service.registerFile(file);

    final decoded = jsonDecode(intakeBody!) as Map<String, dynamic>;
    expect(decoded.containsKey('intake_mode'), isFalse);
  });

  test('inbox local intake sends explicit intake mode', () async {
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
      return http.Response('{}', 404);
    });

    final apiClient = testSecretaryApiClient(mock);
    apiClient.configure(baseUrl: 'https://example.com', token: 'token');
    final service = LocalFileIntakeService(apiClient: apiClient);
    await service.registerFile(file, intakeMode: 'explicit_local');

    final decoded = jsonDecode(intakeBody!) as Map<String, dynamic>;
    expect(decoded['intake_mode'], 'explicit_local');
  });

  test('failed local intake surfaces API error', () async {
    final file = File('${tempDir.path}/fail.txt');
    file.writeAsStringSync('fail');

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

    final apiClient = testSecretaryApiClient(mock);
    apiClient.configure(baseUrl: 'https://example.com', token: 'token');
    final service = LocalFileIntakeService(apiClient: apiClient);
    expect(() => service.registerFile(file), throwsA(isA<ServerException>()));
  });

  test('partial local intake success still registers valid files', () async {
    final okFile = File('${tempDir.path}/ok.txt');
    final badFile = File('${tempDir.path}/bad.txt');
    okFile.writeAsStringSync('ok');
    badFile.writeAsStringSync('bad');

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
      return http.Response('{}', 404);
    });

    final apiClient = testSecretaryApiClient(mock);
    apiClient.configure(baseUrl: 'https://example.com', token: 'token');
    final service = LocalFileIntakeService(apiClient: apiClient);
    final result = await service.registerFile(okFile);
    expect(result.objectId, 'obj-ok');
    expect(() => service.registerFile(badFile), throwsA(isA<ServerException>()));
  });
}
