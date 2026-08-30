import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/auth/token_store.dart';
import 'package:personal_secretary/capture/capture_controller.dart';
import 'package:personal_secretary/inbox/inbox_screen.dart';
import 'package:personal_secretary/inbox/notification_labels.dart';

void main() {
  const baseUrl = 'https://secretary.example';
  const token = 'inbox-token';

  NotificationOut sampleNotification({
    String id = 'n1',
    String status = 'new',
    String priority = 'high',
  }) {
    return NotificationOut.fromJson({
      'id': id,
      'title': 'Follow up email',
      'body': 'Please reply',
      'priority': priority,
      'status': status,
      'source_object_id': 'email-1',
      'related_object_id': null,
      'result_object_id': null,
      'proposal': {
        'type': 'task',
        'description': 'Send reply',
        'action': 'create_task',
        'confidence': 0.9,
        'evidence': [
          {
            'kind': 'email',
            'title': 'Gmail message',
            'why_included': 'matched subject',
          },
        ],
      },
      'read_at': null,
      'created_at': '2026-08-28T10:00:00Z',
      'updated_at': '2026-08-28T10:00:00Z',
    });
  }

  Widget buildInbox(MockClient mock) {
    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    final capture = CaptureController(apiClient: apiClient, authController: auth);
    return MaterialApp(
      home: Scaffold(
        body: InboxScreen(
          apiClient: apiClient,
          authController: auth,
          captureController: capture,
        ),
      ),
    );
  }

  test('evidence source label renders', () {
    final label = notificationEvidenceLabel(sampleNotification());
    expect(label, contains('email'));
    expect(label, contains('Gmail message'));
  });

  testWidgets('unresolved notifications render', (tester) async {
    await tester.pumpWidget(
      buildInbox(MockClient((request) async {
        if (request.url.path == '/notifications' &&
            request.url.queryParameters['status'] == 'unresolved') {
          return http.Response(
            jsonEncode({
              'notifications': [_notificationJson(sampleNotification())],
            }),
            200,
          );
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    expect(find.text('Follow up email'), findsOneWidget);
    expect(find.textContaining('Gmail message'), findsWidgets);
  });

  testWidgets('Accept calls correct endpoint', (tester) async {
    String? acceptedPath;
    await tester.pumpWidget(
      buildInbox(MockClient((request) async {
        if (request.url.path == '/notifications' &&
            request.url.queryParameters['status'] == 'unresolved') {
          return http.Response(
            jsonEncode({'notifications': [_notificationJson(sampleNotification())]}),
            200,
          );
        }
        if (request.method == 'POST' && request.url.path.endsWith('/accept')) {
          acceptedPath = request.url.path;
          return http.Response(
            jsonEncode({
              ..._notificationJson(sampleNotification(status: 'accepted')),
              'status': 'accepted',
            }),
            200,
          );
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Принять'));
    await tester.pumpAndSettle();

    expect(acceptedPath, '/notifications/n1/accept');
    expect(find.text('Follow up email'), findsNothing);
  });

  testWidgets('Ignore calls correct endpoint', (tester) async {
    String? ignoredPath;
    await tester.pumpWidget(
      buildInbox(MockClient((request) async {
        if (request.url.path == '/notifications' &&
            request.url.queryParameters['status'] == 'unresolved') {
          return http.Response(
            jsonEncode({'notifications': [_notificationJson(sampleNotification())]}),
            200,
          );
        }
        if (request.method == 'POST' && request.url.path.endsWith('/ignore')) {
          ignoredPath = request.url.path;
          return http.Response(
            jsonEncode({
              ..._notificationJson(sampleNotification(status: 'ignored')),
              'status': 'ignored',
            }),
            200,
          );
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Пропустить'));
    await tester.pumpAndSettle();

    expect(ignoredPath, '/notifications/n1/ignore');
    expect(find.text('Follow up email'), findsNothing);
  });

  testWidgets('failed mutation leaves item visible', (tester) async {
    await tester.pumpWidget(
      buildInbox(MockClient((request) async {
        if (request.url.path == '/notifications' &&
            request.url.queryParameters['status'] == 'unresolved') {
          return http.Response(
            jsonEncode({'notifications': [_notificationJson(sampleNotification())]}),
            200,
          );
        }
        if (request.method == 'POST' && request.url.path.endsWith('/accept')) {
          return http.Response(jsonEncode({'detail': 'server error'}), 500);
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Принять'));
    await tester.pumpAndSettle();

    expect(find.text('Follow up email'), findsOneWidget);
  });

  testWidgets('401 exits authenticated UI', (tester) async {
    final apiClient = SecretaryApiClient(
      httpClient: MockClient((request) async {
        return http.Response(jsonEncode({'detail': 'unauthorized'}), 401);
      }),
    );
    apiClient.configure(baseUrl: baseUrl, token: token);
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
  auth.user = UserMe(
      id: 'u1',
      displayName: 'Alice',
      createdAt: '2026-01-01T00:00:00Z',
    );
    final capture = CaptureController(apiClient: apiClient, authController: auth);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: InboxScreen(
            apiClient: apiClient,
            authController: auth,
            captureController: capture,
          ),
        ),
      ),
    );
    await tester.pump();

    expect(auth.status, AuthStatus.needsAuth);
  });

  testWidgets('empty state works', (tester) async {
    await tester.pumpWidget(
      buildInbox(MockClient((request) async {
        if (request.url.path == '/notifications') {
          return http.Response(jsonEncode({'notifications': []}), 200);
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    expect(find.text('Входящие пусты'), findsOneWidget);
  });
}

Map<String, dynamic> _notificationJson(NotificationOut notification) {
  return {
    'id': notification.id,
    'title': notification.title,
    'body': notification.body,
    'priority': notification.priority,
    'status': notification.status,
    'source_object_id': notification.sourceObjectId,
    'related_object_id': notification.relatedObjectId,
    'result_object_id': notification.resultObjectId,
    'proposal': notification.proposal,
    'read_at': notification.readAt,
    'created_at': notification.createdAt,
    'updated_at': notification.updatedAt,
  };
}
