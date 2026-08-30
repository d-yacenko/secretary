import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/api/api_error.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';

void main() {
  const baseUrl = 'https://secretary.example';
  const token = 'opaque-test-token-abc123';

  group('SecretaryApiClient', () {
    test('adds bearer Authorization header to authenticated requests', () async {
      String? capturedAuth;
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          capturedAuth = request.headers['Authorization'];
          return http.Response(
            jsonEncode({
              'id': 'user-1',
              'display_name': 'Alice',
              'created_at': '2026-01-01T00:00:00Z',
            }),
            200,
          );
        }),
      );
      client.configure(baseUrl: baseUrl, token: token);
      await client.getMe();
      expect(capturedAuth, 'Bearer $token');
    });

    test('does not add user_id to capture payload', () async {
      Map<String, dynamic>? body;
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          body = jsonDecode(request.body) as Map<String, dynamic>;
          return http.Response(
            jsonEncode({
              'task_id': 'task-1',
              'context_edge_ids': [],
              'dependency_edge_ids': [],
            }),
            201,
          );
        }),
      );
      client.configure(baseUrl: baseUrl, token: token);
      await client.captureTask(CaptureTaskRequest(text: 'Do something'));
      expect(body!.containsKey('user_id'), isFalse);
      expect(body!['text'], 'Do something');
    });

    test('parses /me response', () async {
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          return http.Response(
            jsonEncode({
              'id': 'user-1',
              'display_name': 'Alice',
              'created_at': '2026-01-01T00:00:00Z',
            }),
            200,
          );
        }),
      );
      client.configure(baseUrl: baseUrl, token: token);
      final me = await client.getMe();
      expect(me.id, 'user-1');
      expect(me.displayName, 'Alice');
    });

    test('parses /connections response', () async {
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          return http.Response(
            jsonEncode({
              'google': {
                'connected': true,
                'email': 'alice@gmail.com',
                'gmail_available': true,
                'calendar_available': false,
              },
              'yandex_mail': {'connected': false, 'email': null},
              'yandex_calendar': {'connected': false, 'email': null},
            }),
            200,
          );
        }),
      );
      client.configure(baseUrl: baseUrl, token: token);
      final connections = await client.getConnections();
      expect(connections.google.connected, isTrue);
      expect(connections.google.gmailAvailable, isTrue);
      expect(connections.yandexMail.connected, isFalse);
    });

    test('capture serialization includes text and title', () async {
      final request = CaptureTaskRequest(
        text: '  keep spaces  ',
        title: 'My title',
      );
      final json = request.toJson();
      expect(json['text'], '  keep spaces  ');
      expect(json['title'], 'My title');
    });

    test('capture serialization supports context and dependency IDs', () async {
      final request = CaptureTaskRequest(
        text: 'task',
        contextObjectIds: ['ctx-1', 'ctx-2'],
        dependsOnIds: ['dep-1'],
      );
      final json = request.toJson();
      expect(json['context_object_ids'], ['ctx-1', 'ctx-2']);
      expect(json['depends_on_ids'], ['dep-1']);
    });

    test('401 maps to authentication error', () async {
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          return http.Response(jsonEncode({'detail': 'invalid token'}), 401);
        }),
      );
      client.configure(baseUrl: baseUrl, token: token);
      await expectLater(client.getMe(), throwsA(isA<AuthenticationException>()));
    });

    test('422 maps to validation error', () async {
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          return http.Response(jsonEncode({'detail': 'text must not be empty'}), 422);
        }),
      );
      client.configure(baseUrl: baseUrl, token: token);
      await expectLater(
        client.captureTask(CaptureTaskRequest(text: 'x')),
        throwsA(isA<ValidationException>()),
      );
    });

    test('token never appears in sanitized error text', () async {
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          return http.Response(
            jsonEncode({'detail': 'Bearer $token rejected'}),
            401,
          );
        }),
      );
      client.configure(baseUrl: baseUrl, token: token);
      try {
        await client.getMe();
        fail('expected exception');
      } on AuthenticationException catch (e) {
        expect(e.message.contains(token), isFalse);
        expect(e.message, contains('[redacted]'));
      }
    });

    test('request URLs do not embed bearer token', () async {
      Uri? capturedUri;
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          capturedUri = request.url;
          return http.Response(
            jsonEncode({
              'id': 'user-1',
              'display_name': 'Alice',
              'created_at': '2026-01-01T00:00:00Z',
            }),
            200,
          );
        }),
      );
      client.configure(baseUrl: baseUrl, token: token);
      await client.getMe();
      expect(capturedUri!.toString().contains(token), isFalse);
      expect(capturedUri!.query.contains(token), isFalse);
    });

    test('transcribeAudio sends authenticated multipart audio field', () async {
      String? method;
      Uri? uri;
      String? authorization;
      String bodyText = '';
      final client = SecretaryApiClient(
        httpClient: MockClient((request) async {
          method = request.method;
          uri = request.url;
          authorization = request.headers['Authorization'];
          bodyText = utf8.decode(request.bodyBytes, allowMalformed: true);
          return http.Response(jsonEncode({'text': 'recognized speech'}), 200);
        }),
      );
      client.configure(baseUrl: baseUrl, token: token);
      final text = await client.transcribeAudio(
        audioBytes: [1, 2, 3, 4],
        filename: 'secretary_voice.wav',
        contentType: 'audio/wav',
      );
      expect(text, 'recognized speech');
      expect(method, 'POST');
      expect(uri?.path, '/assistant/transcribe');
      expect(authorization, 'Bearer $token');
      expect(bodyText, contains('name="audio"'));
      expect(bodyText, contains('secretary_voice.wav'));
      expect(bodyText.toLowerCase(), contains('content-type: audio/wav'));
    });

    group('safe URL composition', () {
      Map<String, dynamic> connectionsJson() => {
            'google': {
              'connected': false,
              'gmail_available': false,
              'calendar_available': false,
            },
            'yandex_mail': {'connected': false},
            'yandex_calendar': {'connected': false},
          };

      Future<Uri> captureRequestUri(String base, String endpoint) async {
        Uri? capturedUri;
        final client = SecretaryApiClient(
          httpClient: MockClient((request) async {
            capturedUri = request.url;
            if (endpoint == '/capture/task') {
              return http.Response(
                jsonEncode({
                  'task_id': 'task-1',
                  'context_edge_ids': [],
                  'dependency_edge_ids': [],
                }),
                201,
              );
            }
            if (endpoint == '/connections') {
              return http.Response(jsonEncode(connectionsJson()), 200);
            }
            return http.Response(
              jsonEncode({
                'id': 'user-1',
                'display_name': 'Alice',
                'created_at': '2026-01-01T00:00:00Z',
              }),
              200,
            );
          }),
        );
        client.configure(baseUrl: base, token: token);
        switch (endpoint) {
          case '/me':
            await client.getMe();
          case '/connections':
            await client.getConnections();
          case '/capture/task':
            await client.captureTask(CaptureTaskRequest(text: 'x'));
        }
        return capturedUri!;
      }

      test('https://host/ resolves /me', () async {
        final uri = await captureRequestUri('https://host/', '/me');
        expect(uri.toString(), 'https://host/me');
        expect(uri.query.contains(token), isFalse);
      });

      test('https://host/// resolves /me', () async {
        final uri = await captureRequestUri('https://host///', '/me');
        expect(uri.toString(), 'https://host/me');
      });

      test('https://host/api resolves endpoints', () async {
        expect(
          (await captureRequestUri('https://host/api', '/me')).toString(),
          'https://host/api/me',
        );
        expect(
          (await captureRequestUri('https://host/api/', '/connections')).toString(),
          'https://host/api/connections',
        );
        expect(
          (await captureRequestUri('https://host/api/', '/capture/task')).toString(),
          'https://host/api/capture/task',
        );
      });

      test('rejects query and fragment base URLs', () {
        final client = SecretaryApiClient();
        expect(
          () => client.configure(baseUrl: 'https://host?x=1', token: token),
          throwsArgumentError,
        );
        expect(
          () => client.configure(baseUrl: 'https://host#frag', token: token),
          throwsArgumentError,
        );
      });
    });
  });
}
