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

  Map<String, dynamic> inboxJson({
    List<Map<String, dynamic>>? notifications,
    List<Map<String, dynamic>>? recentSources,
    List<Map<String, dynamic>>? syncStatus,
  }) {
    return {
      'unresolved_notifications': notifications ?? [],
      'recent_source_objects': recentSources ?? [],
      'source_sync_status': syncStatus ?? [],
    };
  }

  Map<String, dynamic> syncStatusJson({
    String provider = 'gmail',
    String status = 'error',
    String accountLabel = 'user@example.com',
    String? lastError = 'RuntimeError',
    String? lastSuccessAt = '2026-09-01T10:00:00Z',
    String? lastAttemptAt = '2026-09-02T09:00:00Z',
  }) {
    return {
      'source': provider,
      'provider': provider,
      'account_id': '550e8400-e29b-41d4-a716-446655440000',
      'account_label': accountLabel,
      'status': status,
      'last_success_at': lastSuccessAt,
      'last_attempt_at': lastAttemptAt,
      'next_sync_at': null,
      'last_error': lastError,
    };
  }

  Widget buildInbox(
    MockClient mock, {
    Duration passiveRefreshInterval = const Duration(seconds: 30),
  }) {
    final apiClient = SecretaryApiClient(httpClient: mock);
    apiClient.configure(baseUrl: baseUrl, token: token);
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    final capture =
        CaptureController(apiClient: apiClient, authController: auth);
    return MaterialApp(
      home: Scaffold(
        body: InboxScreen(
          apiClient: apiClient,
          authController: auth,
          captureController: capture,
          passiveRefreshInterval: passiveRefreshInterval,
        ),
      ),
    );
  }

  test('evidence source label renders', () {
    final label = notificationEvidenceLabel(sampleNotification());
    expect(label, contains('Письмо'));
    expect(label, contains('Gmail message'));
  });

  testWidgets('unresolved notifications render', (tester) async {
    await tester.pumpWidget(
      buildInbox(MockClient((request) async {
        if (request.url.path == '/inbox') {
          return http.Response(
            jsonEncode(inboxJson(
              notifications: [_notificationJson(sampleNotification())],
            )),
            200,
          );
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    expect(find.text('Follow up email'), findsOneWidget);
    expect(find.text('Требует внимания'), findsOneWidget);
  });

  testWidgets('Accept calls correct endpoint', (tester) async {
    String? acceptedPath;
    await tester.pumpWidget(
      buildInbox(MockClient((request) async {
        if (request.url.path == '/inbox') {
          return http.Response(
            jsonEncode(inboxJson(
              notifications: [_notificationJson(sampleNotification())],
            )),
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
        if (request.url.path == '/inbox') {
          return http.Response(
            jsonEncode(inboxJson(
              notifications: [_notificationJson(sampleNotification())],
            )),
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
        if (request.url.path == '/inbox') {
          return http.Response(
            jsonEncode(inboxJson(
              notifications: [_notificationJson(sampleNotification())],
            )),
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
    final capture =
        CaptureController(apiClient: apiClient, authController: auth);

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

  testWidgets('empty state when both sections empty', (tester) async {
    await tester.pumpWidget(
      buildInbox(MockClient((request) async {
        if (request.url.path == '/inbox') {
          return http.Response(jsonEncode(inboxJson()), 200);
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    expect(find.text('Входящие пусты'), findsOneWidget);
  });

  testWidgets('recent source section without notifications', (tester) async {
    await tester.pumpWidget(
      buildInbox(MockClient((request) async {
        if (request.url.path == '/inbox') {
          return http.Response(
            jsonEncode(inboxJson(
              recentSources: [
                {
                  'id': 'email-1',
                  'title': 'VPN marker email',
                  'kind': 'email',
                  'provider': 'gmail',
                  'state': 'confirmed',
                  'status': null,
                  'primary_at': '2026-08-31T10:00:00Z',
                  'excerpt': 'body excerpt',
                },
              ],
            )),
            200,
          );
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    expect(find.text('Входящие пусты'), findsNothing);
    expect(find.text('VPN marker email'), findsOneWidget);
    expect(find.text('Последние из источников'), findsOneWidget);
    expect(find.textContaining('Событие •'), findsNothing);
    expect(find.textContaining('Яндекс Календарь'), findsNothing);
  });

  testWidgets('source card uses single compact header row', (tester) async {
    await tester.pumpWidget(
      buildInbox(MockClient((request) async {
        if (request.url.path == '/inbox') {
          return http.Response.bytes(
            utf8.encode(jsonEncode(inboxJson(
              recentSources: [
                {
                  'id': 'event-1',
                  'title': 'Дима — Синхронизация',
                  'kind': 'event',
                  'provider': 'yandex_calendar',
                  'state': 'observed',
                  'status': null,
                  'primary_at': '2026-09-02T10:30:00Z',
                  'excerpt': 'Ссылка на видеовстречу',
                },
              ],
            ))),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'},
          );
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    expect(find.text('Дима — Синхронизация'), findsOneWidget);
    expect(find.text('Я'), findsOneWidget);
    expect(find.textContaining('02.09.2026'), findsOneWidget);
    expect(find.textContaining('Событие •'), findsNothing);
  });

  testWidgets('passive refresh loads newer inbox snapshot without navigation',
      (tester) async {
    int inboxCalls = 0;
    await tester.pumpWidget(
      buildInbox(
        MockClient((request) async {
          if (request.url.path == '/inbox') {
            inboxCalls++;
            final sources = inboxCalls == 1
                ? [
                    {
                      'id': 'email-a',
                      'title': 'Snapshot email A',
                      'kind': 'email',
                      'provider': 'gmail',
                      'state': 'observed',
                      'status': null,
                      'primary_at': '2026-08-31T10:00:00Z',
                      'excerpt': 'first',
                    },
                  ]
                : [
                    {
                      'id': 'email-a',
                      'title': 'Snapshot email A',
                      'kind': 'email',
                      'provider': 'gmail',
                      'state': 'observed',
                      'status': null,
                      'primary_at': '2026-08-31T10:00:00Z',
                      'excerpt': 'first',
                    },
                    {
                      'id': 'email-b',
                      'title': 'Snapshot email B',
                      'kind': 'email',
                      'provider': 'gmail',
                      'state': 'observed',
                      'status': null,
                      'primary_at': '2026-08-31T11:00:00Z',
                      'excerpt': 'second',
                    },
                  ];
            return http.Response(
                jsonEncode(inboxJson(recentSources: sources)), 200);
          }
          return http.Response('{}', 404);
        }),
        passiveRefreshInterval: const Duration(seconds: 5),
      ),
    );
    for (var i = 0; i < 30; i++) {
      await tester.pump(const Duration(milliseconds: 10));
      if (find.text('Snapshot email A').evaluate().isNotEmpty) {
        break;
      }
    }

    expect(inboxCalls, 1);
    expect(find.text('Snapshot email A'), findsOneWidget);
    expect(find.text('Snapshot email B'), findsNothing);

    await tester.pump(const Duration(seconds: 5));
    await tester.pump();

    expect(inboxCalls, 2);
    expect(find.text('Snapshot email B'), findsOneWidget);
  });

  testWidgets('passive refresh does not call sources sync', (tester) async {
    int inboxCalls = 0;
    int syncCalls = 0;
    await tester.pumpWidget(
      buildInbox(
        MockClient((request) async {
          if (request.url.path == '/inbox') {
            inboxCalls++;
            return http.Response(jsonEncode(inboxJson()), 200);
          }
          if (request.url.path == '/sources/sync') {
            syncCalls++;
            return http.Response('{"triggered":[],"count":0}', 200);
          }
          return http.Response('{}', 404);
        }),
        passiveRefreshInterval: const Duration(seconds: 5),
      ),
    );
    await tester.pumpAndSettle();
    await tester.pump(const Duration(seconds: 5));
    await tester.pump();

    expect(inboxCalls, greaterThan(1));
    expect(syncCalls, 0);
  });

  testWidgets('passive refresh preserves snapshot on transient error',
      (tester) async {
    int inboxCalls = 0;
    await tester.pumpWidget(
      buildInbox(
        MockClient((request) async {
          if (request.url.path == '/inbox') {
            inboxCalls++;
            if (inboxCalls >= 2) {
              return http.Response('server error', 500);
            }
            return http.Response(
              jsonEncode(inboxJson(
                recentSources: [
                  {
                    'id': 'email-stable',
                    'title': 'Stable inbox row',
                    'kind': 'email',
                    'provider': 'gmail',
                    'state': 'observed',
                    'status': null,
                    'primary_at': '2026-08-31T10:00:00Z',
                    'excerpt': 'stable',
                  },
                ],
              )),
              200,
            );
          }
          return http.Response('{}', 404);
        }),
        passiveRefreshInterval: const Duration(seconds: 5),
      ),
    );
    for (var i = 0; i < 30; i++) {
      await tester.pump(const Duration(milliseconds: 10));
      if (find.text('Stable inbox row').evaluate().isNotEmpty) {
        break;
      }
    }
    expect(find.text('Stable inbox row'), findsOneWidget);

    await tester.pump(const Duration(seconds: 5));
    await tester.pump();

    expect(find.text('Stable inbox row'), findsOneWidget);
    expect(find.text('Ошибка загрузки'), findsNothing);
  });

  testWidgets('one failing source shows provider account and safe reason',
      (tester) async {
    const leakMarker = 'sk-testPhase28bDLeakMarker';
    await tester.pumpWidget(
      buildInbox(MockClient((request) async {
        if (request.url.path == '/inbox') {
          return http.Response(
            jsonEncode(inboxJson(
              syncStatus: [
                syncStatusJson(lastError: leakMarker),
              ],
            )),
            200,
          );
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    expect(find.text('Gmail — user@example.com'), findsOneWidget);
    expect(find.textContaining('Ошибка синхронизации'), findsOneWidget);
    expect(find.textContaining(leakMarker), findsNothing);
    expect(find.textContaining('Последняя успешная синхронизация'),
        findsOneWidget);
  });

  testWidgets('multiple failing sources are represented', (tester) async {
    await tester.pumpWidget(
      buildInbox(MockClient((request) async {
        if (request.url.path == '/inbox') {
          return http.Response(
            jsonEncode(inboxJson(
              syncStatus: [
                syncStatusJson(provider: 'gmail'),
                syncStatusJson(
                  provider: 'mattermost',
                  accountLabel: 'Alice @ mm.example.com',
                  lastError: 'ConnectionError',
                ),
              ],
            )),
            200,
          );
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    expect(find.text('Gmail — user@example.com'), findsOneWidget);
    expect(find.text('Mattermost — Alice @ mm.example.com'), findsOneWidget);
  });

  testWidgets('non-error sync statuses do not show error card', (tester) async {
    await tester.pumpWidget(
      buildInbox(MockClient((request) async {
        if (request.url.path == '/inbox') {
          return http.Response(
            jsonEncode(inboxJson(
              syncStatus: [
                syncStatusJson(
                  status: 'scheduled',
                  lastError: null,
                  lastSuccessAt: '2026-09-01T10:00:00Z',
                ),
              ],
            )),
            200,
          );
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('Ошибка синхронизации'), findsNothing);
  });

  testWidgets('source errors remain visible when inbox is empty',
      (tester) async {
    await tester.pumpWidget(
      buildInbox(MockClient((request) async {
        if (request.url.path == '/inbox') {
          return http.Response(
            jsonEncode(inboxJson(
              syncStatus: [syncStatusJson()],
            )),
            200,
          );
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();

    expect(find.text('Входящие пусты'), findsNothing);
    expect(find.text('Gmail — user@example.com'), findsOneWidget);
    expect(find.text('Нет уведомлений'), findsOneWidget);
    expect(find.text('Нет недавних объектов из источников'), findsOneWidget);
  });

  testWidgets('manual source refresh failure resets refreshing state',
      (tester) async {
    await tester.pumpWidget(
      buildInbox(MockClient((request) async {
        if (request.url.path == '/inbox') {
          return http.Response(
            jsonEncode(inboxJson(
              recentSources: [
                {
                  'id': 'email-stable',
                  'title': 'Stable inbox row',
                  'kind': 'email',
                  'provider': 'gmail',
                  'state': 'observed',
                  'status': null,
                  'primary_at': '2026-08-31T10:00:00Z',
                  'excerpt': 'stable',
                },
              ],
            )),
            200,
          );
        }
        if (request.method == 'POST' &&
            request.url.path.endsWith('/sources/sync')) {
          return http.Response(jsonEncode({'detail': 'sync failed'}), 500);
        }
        return http.Response('{}', 404);
      })),
    );
    await tester.pumpAndSettle();
    expect(find.text('Stable inbox row'), findsOneWidget);

    await tester.tap(find.byTooltip('Обновить'));
    await tester.pumpAndSettle();

    expect(find.text('Stable inbox row'), findsOneWidget);
    expect(find.byTooltip('Обновить'), findsOneWidget);
  });

  testWidgets('later passive refresh still occurs after manual refresh failure',
      (tester) async {
    int inboxCalls = 0;
    var syncFails = true;
    await tester.pumpWidget(
      buildInbox(
        MockClient((request) async {
          if (request.url.path == '/inbox') {
            inboxCalls++;
            return http.Response(
              jsonEncode(inboxJson(
                recentSources: [
                  {
                    'id': 'email-stable',
                    'title': inboxCalls == 1
                        ? 'Stable inbox row'
                        : 'Updated inbox row',
                    'kind': 'email',
                    'provider': 'gmail',
                    'state': 'observed',
                    'status': null,
                    'primary_at': '2026-08-31T10:00:00Z',
                    'excerpt': 'stable',
                  },
                ],
              )),
              200,
            );
          }
          if (request.method == 'POST' &&
              request.url.path.endsWith('/sources/sync')) {
            if (syncFails) {
              return http.Response(jsonEncode({'detail': 'sync failed'}), 500);
            }
            return http.Response(
                jsonEncode({'triggered': [], 'count': 0}), 200);
          }
          if (request.url.path.endsWith('/sources/status')) {
            return http.Response(jsonEncode({'sources': []}), 200);
          }
          return http.Response('{}', 404);
        }),
        passiveRefreshInterval: const Duration(seconds: 5),
      ),
    );
    await tester.pumpAndSettle();
    expect(inboxCalls, 1);

    await tester.tap(find.byTooltip('Обновить'));
    await tester.pumpAndSettle();
    syncFails = false;
    expect(find.text('Stable inbox row'), findsOneWidget);

    await tester.pump(const Duration(seconds: 5));
    await tester.pump();

    expect(inboxCalls, greaterThan(1));
    expect(find.text('Updated inbox row'), findsOneWidget);
  });

  testWidgets(
      'manual source refresh overlapping passive tick does not kill polling',
      (tester) async {
    int inboxCalls = 0;
    await tester.pumpWidget(
      buildInbox(
        MockClient((request) async {
          if (request.url.path == '/inbox') {
            inboxCalls++;
            return http.Response(
              jsonEncode(inboxJson(
                recentSources: [
                  {
                    'id': 'email-stable',
                    'title': inboxCalls <= 2
                        ? 'Stable inbox row'
                        : 'Passive updated row',
                    'kind': 'email',
                    'provider': 'gmail',
                    'state': 'observed',
                    'status': null,
                    'primary_at': '2026-08-31T10:00:00Z',
                    'excerpt': 'stable',
                  },
                ],
              )),
              200,
            );
          }
          if (request.method == 'POST' &&
              request.url.path.endsWith('/sources/sync')) {
            await Future<void>.delayed(const Duration(milliseconds: 200));
            return http.Response(
                jsonEncode({'triggered': [], 'count': 0}), 200);
          }
          if (request.url.path.endsWith('/sources/status')) {
            await Future<void>.delayed(const Duration(milliseconds: 200));
            return http.Response(jsonEncode({'sources': []}), 200);
          }
          return http.Response('{}', 404);
        }),
        passiveRefreshInterval: const Duration(seconds: 5),
      ),
    );
    await tester.pumpAndSettle();
    expect(inboxCalls, 1);

    await tester.tap(find.byTooltip('Обновить'));
    await tester.pump(const Duration(seconds: 5));
    await tester.pump();

    expect(inboxCalls, greaterThan(2));
    expect(find.text('Passive updated row'), findsOneWidget);
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
