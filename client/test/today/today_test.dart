import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/token_store.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/capture/capture_controller.dart';
import 'package:personal_secretary/objects/object_detail_screen.dart';
import 'package:personal_secretary/today/today_screen.dart';

void main() {
  const baseUrl = 'https://secretary.example';
  const token = 'today-token';

  Map<String, dynamic> todayPayload({List<Map<String, dynamic>>? tasks}) {
    return {
      'date': '2026-08-28',
      'timezone': 'Europe/Amsterdam',
      'day_start': '2026-08-28T00:00:00+02:00',
      'tasks': tasks ??
          [
        {
          'id': 'task-1',
          'kind': 'task',
          'title': 'Due today',
          'body': null,
          'provider': null,
          'external_id': null,
          'canonical_uri': null,
          'status': null,
          'start_at': null,
          'due_at': '2026-08-28T14:00:00+02:00',
          'metadata': {},
          'origin': 'user',
          'state': 'confirmed',
          'confidence': null,
          'created_at': '2026-08-28T08:00:00Z',
          'updated_at': '2026-08-28T08:00:00Z',
        },
      ],
      'calendar_events': [
        {
          'id': 'event-1',
          'kind': 'event',
          'title': 'Standup',
          'body': null,
          'provider': 'google',
          'external_id': null,
          'canonical_uri': null,
          'status': null,
          'start_at': '2026-08-28T09:00:00+02:00',
          'due_at': '2026-08-28T10:00:00+02:00',
          'metadata': {},
          'origin': 'source',
          'state': 'observed',
          'confidence': null,
          'created_at': '2026-08-28T08:00:00Z',
          'updated_at': '2026-08-28T08:00:00Z',
        },
      ],
      'notifications': [
        {
          'id': 'n-urgent',
          'title': 'Urgent follow-up',
          'body': null,
          'priority': 'urgent',
          'status': 'new',
          'source_object_id': 'email-1',
          'related_object_id': null,
          'result_object_id': null,
          'proposal': {
            'type': 'task',
            'confidence': 0.9,
            'evidence': [],
          },
          'read_at': null,
          'created_at': '2026-08-28T08:00:00Z',
          'updated_at': '2026-08-28T08:00:00Z',
        },
      ],
    };
  }

  Widget buildToday(MockClient mock) {
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
        body: TodayScreen(
          apiClient: apiClient,
          authController: auth,
          captureController: capture,
        ),
      ),
    );
  }

  testWidgets('tasks calendar and notifications render', (tester) async {
    await tester.pumpWidget(
      buildToday(MockClient((request) async {
        if (request.url.path == '/today') {
          return http.Response(jsonEncode(todayPayload()), 200);
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    expect(find.text('Due today'), findsOneWidget);
    expect(find.text('Standup'), findsOneWidget);
    expect(find.text('Urgent follow-up'), findsOneWidget);
  });

  testWidgets('empty sections work', (tester) async {
    await tester.pumpWidget(
      buildToday(MockClient((request) async {
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
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    expect(find.text('No tasks for today'), findsOneWidget);
    expect(find.text('No calendar events today'), findsOneWidget);
    expect(find.text('No important notifications'), findsOneWidget);
  });

  testWidgets('refresh works', (tester) async {
    var calls = 0;
    await tester.pumpWidget(
      buildToday(MockClient((request) async {
        if (request.url.path == '/today') {
          calls += 1;
          return http.Response(jsonEncode(todayPayload()), 200);
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();
    expect(calls, 1);

    await tester.tap(find.byTooltip('Refresh'));
    await tester.pumpAndSettle();
    expect(calls, 2);
  });

  testWidgets('tapping task opens Object Detail', (tester) async {
    await tester.pumpWidget(
      buildToday(MockClient((request) async {
        if (request.url.path == '/today') {
          return http.Response(jsonEncode(todayPayload()), 200);
        }
        if (request.url.path == '/objects/task-1') {
          return http.Response(
            jsonEncode({
              'id': 'task-1',
              'kind': 'task',
              'title': 'Due today',
              'body': null,
              'provider': null,
              'external_id': null,
              'canonical_uri': null,
              'status': null,
              'start_at': null,
              'due_at': '2026-08-28T14:00:00+02:00',
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
        if (request.url.path == '/objects/task-1/neighbors') {
          return http.Response(
            jsonEncode({'object_id': 'task-1', 'neighbors': []}),
            200,
          );
        }
        if (request.url.path == '/objects/task-1/context') {
          return http.Response(
            jsonEncode({
              'object': {
                'id': 'task-1',
                'kind': 'task',
                'title': 'Due today',
                'body': null,
                'provider': null,
                'external_id': null,
                'canonical_uri': null,
                'status': null,
                'start_at': null,
                'due_at': '2026-08-28T14:00:00+02:00',
                'metadata': {},
                'origin': 'user',
                'state': 'confirmed',
                'confidence': null,
                'created_at': '2026-08-28T08:00:00Z',
                'updated_at': '2026-08-28T08:00:00Z',
              },
              'edges': [],
              'neighbors': [],
            }),
            200,
          );
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Due today'));
    await tester.pumpAndSettle();

    expect(find.byType(ObjectDetailScreen), findsOneWidget);
    expect(find.text('Use as task context'), findsOneWidget);
  });

  test('isTaskOverdue compares due_at against day_start instant', () {
    final early = SecretaryObject.fromJson({
      'id': 'task-early',
      'kind': 'task',
      'title': 'Early today',
      'body': null,
      'provider': null,
      'external_id': null,
      'canonical_uri': null,
      'status': null,
      'start_at': null,
      'due_at': '2026-08-29T00:30:00+02:00',
      'metadata': {},
      'origin': 'user',
      'state': 'confirmed',
      'confidence': null,
      'created_at': '2026-08-28T08:00:00Z',
      'updated_at': '2026-08-28T08:00:00Z',
    });
    final late = SecretaryObject.fromJson({
      'id': 'task-late',
      'kind': 'task',
      'title': 'Late yesterday',
      'body': null,
      'provider': null,
      'external_id': null,
      'canonical_uri': null,
      'status': null,
      'start_at': null,
      'due_at': '2026-08-28T23:30:00+02:00',
      'metadata': {},
      'origin': 'user',
      'state': 'confirmed',
      'confidence': null,
      'created_at': '2026-08-28T08:00:00Z',
      'updated_at': '2026-08-28T08:00:00Z',
    });

    final todayAug29 = TodayOut.fromJson({
      'date': '2026-08-29',
      'timezone': 'Europe/Amsterdam',
      'day_start': '2026-08-29T00:00:00+02:00',
      'tasks': [],
      'calendar_events': [],
      'notifications': [],
    });

    expect(todayAug29.isTaskOverdue(early), isFalse);
    expect(todayAug29.isTaskOverdue(late), isTrue);
  });

  testWidgets('overdue label uses day_start not device timezone', (tester) async {
    await tester.pumpWidget(
      buildToday(MockClient((request) async {
        if (request.url.path == '/today') {
          return http.Response(
            jsonEncode({
              'date': '2026-08-29',
              'timezone': 'Europe/Amsterdam',
              'day_start': '2026-08-29T00:00:00+02:00',
              'tasks': [
                {
                  'id': 'task-late',
                  'kind': 'task',
                  'title': 'Late yesterday',
                  'body': null,
                  'provider': null,
                  'external_id': null,
                  'canonical_uri': null,
                  'status': null,
                  'start_at': null,
                  'due_at': '2026-08-28T23:30:00+02:00',
                  'metadata': {},
                  'origin': 'user',
                  'state': 'confirmed',
                  'confidence': null,
                  'created_at': '2026-08-28T08:00:00Z',
                  'updated_at': '2026-08-28T08:00:00Z',
                },
              ],
              'calendar_events': [],
              'notifications': [],
            }),
            200,
          );
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('Overdue'), findsOneWidget);
  });
}
