import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/auth/token_store.dart';
import 'package:personal_secretary/capture/capture_controller.dart';
import 'package:personal_secretary/objects/object_detail_screen.dart';
import 'package:personal_secretary/today/temporal_area.dart';
import 'package:personal_secretary/today/today_screen.dart';
import 'package:personal_secretary/today/week_screen.dart';
import 'package:personal_secretary/ui/date_format.dart';

void main() {
  const baseUrl = 'https://secretary.example';
  const token = 'week-token';

  Map<String, dynamic> secretaryObjectJson({
    required String id,
    required String title,
    String kind = 'event',
    String? provider = 'google_calendar',
    String? startAt,
    String? dueAt,
    bool allDay = false,
    bool includeAllDay = true,
  }) {
    return {
      'id': id,
      'kind': kind,
      'title': title,
      'body': null,
      'provider': provider,
      'external_id': null,
      'canonical_uri': null,
      'status': null,
      'start_at': startAt,
      'due_at': dueAt,
      'occurred_at': startAt,
      'metadata': {},
      'origin': 'source',
      'state': 'observed',
      'confidence': null,
      'created_at': '2026-09-07T08:00:00Z',
      'updated_at': '2026-09-07T08:00:00Z',
      if (includeAllDay) 'all_day': allDay,
    };
  }

  Map<String, dynamic> weekPayload({
    String weekStart = '2026-09-07',
    bool isCurrentWeek = true,
    String todayDate = '2026-09-10',
    Map<String, List<Map<String, dynamic>>> eventsByDate = const {},
  }) {
    final start = parseCalendarDate(weekStart);
    return {
      'week_start': weekStart,
      'week_end': formatCalendarDate(start.add(const Duration(days: 7))),
      'timezone': 'Europe/Amsterdam',
      'window_start': '${weekStart}T00:00:00+02:00',
      'window_end':
          '${formatCalendarDate(start.add(const Duration(days: 7)))}T00:00:00+02:00',
      'today_date': todayDate,
      'is_current_week': isCurrentWeek,
      'days': [
        for (var i = 0; i < 7; i++)
          {
            'date': formatCalendarDate(start.add(Duration(days: i))),
            'is_today': formatCalendarDate(start.add(Duration(days: i))) ==
                todayDate,
            'events': eventsByDate[
                    formatCalendarDate(start.add(Duration(days: i)))] ??
                const [],
          },
      ],
    };
  }

  Map<String, dynamic> todayPayload() {
    return {
      'date': '2026-09-10',
      'timezone': 'Europe/Amsterdam',
      'day_start': '2026-09-10T00:00:00+02:00',
      'tasks': [
        secretaryObjectJson(
          id: 'task-1',
          title: 'Due today',
          kind: 'task',
          provider: null,
          dueAt: '2026-09-10T14:00:00+02:00',
          includeAllDay: false,
        ),
      ],
      'calendar_events': [
        secretaryObjectJson(
          id: 'today-event-1',
          title: 'Standup',
          startAt: '2026-09-10T09:00:00+02:00',
          dueAt: '2026-09-10T10:00:00+02:00',
          includeAllDay: false,
        ),
      ],
      'notifications': [],
    };
  }

  http.Response jsonOk(Object body) =>
      http.Response(jsonEncode(body), 200, headers: {'content-type': 'application/json'});

  Widget harness({
    required Widget child,
    Size size = const Size(360, 760),
    TextScaler textScaler = TextScaler.noScaling,
  }) {
    return MaterialApp(
      home: MediaQuery(
        data: MediaQueryData(size: size, textScaler: textScaler),
        child: Scaffold(body: child),
      ),
    );
  }

  (AuthController, CaptureController) controllers(MockClient mock) {
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
    return (auth, capture);
  }

  Widget buildWeek(MockClient mock, {Size size = const Size(360, 760)}) {
    final pair = controllers(mock);
    return harness(
      size: size,
      child: WeekScreen(
        apiClient: pair.$1.apiClient,
        authController: pair.$1,
        captureController: pair.$2,
      ),
    );
  }

  Widget buildTemporal(MockClient mock, {Size size = const Size(360, 760)}) {
    final pair = controllers(mock);
    return harness(
      size: size,
      child: TemporalArea(
        apiClient: pair.$1.apiClient,
        authController: pair.$1,
        captureController: pair.$2,
        passiveRefreshInterval: const Duration(days: 1),
        clockTick: const Duration(days: 1),
      ),
    );
  }

  MockClient weekClient({
    required Map<String, dynamic> Function(String? weekStart) week,
  }) {
    return MockClient((request) async {
      if (request.url.path == '/week') {
        return jsonOk(week(request.url.queryParameters['week_start']));
      }
      if (request.url.path == '/today') {
        return jsonOk(todayPayload());
      }
      if (request.url.path == '/labels/by-objects' ||
          request.url.path == '/object-bookmarks/by-objects') {
        return jsonOk({'objects': {}});
      }
      if (request.url.path.startsWith('/objects/') &&
          request.url.path.endsWith('/neighbors')) {
        final id = request.url.path.split('/')[2];
        return jsonOk({'object_id': id, 'neighbors': []});
      }
      if (request.url.path.startsWith('/objects/') &&
          request.url.path.endsWith('/context')) {
        final id = request.url.path.split('/')[2];
        return jsonOk({
          'object': secretaryObjectJson(
            id: id,
            title: 'Office',
            startAt: '2026-09-07T10:00:00+02:00',
            dueAt: '2026-09-07T11:00:00+02:00',
            includeAllDay: false,
          ),
          'edges': [],
          'neighbors': [],
        });
      }
      if (request.url.path.startsWith('/objects/')) {
        final id = request.url.path.split('/').last;
        return jsonOk(
          secretaryObjectJson(
            id: id,
            title: 'Office',
            startAt: '2026-09-07T10:00:00+02:00',
            dueAt: '2026-09-07T11:00:00+02:00',
            includeAllDay: false,
          ),
        );
      }
      return http.Response('{}', 404);
    });
  }

  test('formatWeekRange uses Monday-Sunday local dates', () {
    expect(formatWeekRange('2026-09-07'), '7–13 сентября');
    expect(formatWeekRange('2026-08-31'), '31 августа – 6 сентября');
  });

  testWidgets('Сегодня | Неделя switch keeps Today and loads Week',
      (tester) async {
    var todayCalls = 0;
    var weekCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/today') {
        todayCalls += 1;
        return jsonOk(todayPayload());
      }
      if (request.url.path == '/week') {
        weekCalls += 1;
        return jsonOk(weekPayload());
      }
      if (request.url.path == '/labels/by-objects' ||
          request.url.path == '/object-bookmarks/by-objects') {
        return jsonOk({'objects': {}});
      }
      return http.Response('{}', 404);
    });
    await tester.pumpWidget(buildTemporal(mock));
    await tester.pumpAndSettle();

    expect(find.byType(TodayScreen), findsOneWidget);
    expect(find.text('Due today'), findsOneWidget);
    expect(find.text('Standup'), findsOneWidget);
    expect(find.text('Неделя'), findsOneWidget);
    expect(todayCalls, 1);
    expect(weekCalls, 0);

    await tester.tap(find.text('Неделя'));
    await tester.pumpAndSettle();
    expect(find.byType(WeekScreen), findsOneWidget);
    expect(find.text('На этой неделе событий нет'), findsOneWidget);
    expect(weekCalls, 1);
    expect(todayCalls, 1);

    await tester.tap(find.text('Сегодня').last);
    await tester.pumpAndSettle();
    expect(find.text('Due today'), findsOneWidget);
    expect(find.text('Standup'), findsOneWidget);
    expect(todayCalls, 1);
  });

  testWidgets('Monday-Sunday order, merge, all-day order, empty days',
      (tester) async {
    tester.view.physicalSize = const Size(360, 2000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final payload = weekPayload(
      todayDate: '2026-09-07',
      eventsByDate: {
        '2026-09-07': [
          secretaryObjectJson(
            id: 'all-day',
            title: 'Holiday',
            allDay: true,
            startAt: '2026-09-07T00:00:00Z',
            dueAt: '2026-09-08T00:00:00Z',
          ),
          secretaryObjectJson(
            id: 'yandex',
            title: 'Yandex standup',
            provider: 'yandex_calendar',
            startAt: '2026-09-07T09:00:00+02:00',
            dueAt: '2026-09-07T09:30:00+02:00',
          ),
          secretaryObjectJson(
            id: 'google',
            title: 'Google review',
            startAt: '2026-09-07T10:00:00+02:00',
            dueAt: '2026-09-07T11:00:00+02:00',
          ),
          secretaryObjectJson(
            id: 'google-overlap',
            title: 'Google overlap',
            startAt: '2026-09-07T10:30:00+02:00',
            dueAt: '2026-09-07T11:30:00+02:00',
          ),
        ],
      },
    );
    await tester.pumpWidget(
      buildWeek(
        weekClient(week: (_) => payload),
        size: const Size(360, 2000),
      ),
    );
    await tester.pumpAndSettle();

    const dates = [
      '2026-09-07',
      '2026-09-08',
      '2026-09-09',
      '2026-09-10',
      '2026-09-11',
      '2026-09-12',
      '2026-09-13',
    ];
    for (var i = 1; i < dates.length; i++) {
      expect(
        tester.getTopLeft(find.byKey(Key('week_day_${dates[i]}'))).dy,
        greaterThan(tester.getTopLeft(find.byKey(Key('week_day_${dates[i - 1]}'))).dy),
      );
    }
    expect(find.text('Пн 7 сентября'), findsOneWidget);
    expect(find.text('Вс 13 сентября'), findsOneWidget);
    expect(
      tester.getTopLeft(find.byKey(const Key('week_event_all-day'))).dy,
      lessThan(tester.getTopLeft(find.byKey(const Key('week_event_yandex'))).dy),
    );
    expect(
      tester.getTopLeft(find.byKey(const Key('week_event_yandex'))).dy,
      lessThan(tester.getTopLeft(find.byKey(const Key('week_event_google'))).dy),
    );
    expect(find.text('Holiday'), findsOneWidget);
    expect(find.text('Весь день'), findsOneWidget);
    expect(find.text('Yandex standup'), findsOneWidget);
    expect(find.text('Google review'), findsOneWidget);
    expect(find.text('Google overlap'), findsOneWidget);
    expect(find.byKey(const Key('source_mark_google')), findsWidgets);
    expect(find.byKey(const Key('source_mark_yandex')), findsOneWidget);
    expect(find.byKey(const Key('week_day_today_2026-09-07')), findsOneWidget);
    expect(find.text('На этой неделе событий нет'), findsNothing);
  });

  testWidgets('previous and next week query Monday starts', (tester) async {
    final requested = <String?>[];
    await tester.pumpWidget(
      buildWeek(
        weekClient(
          week: (weekStart) {
            requested.add(weekStart);
            if (weekStart == '2026-08-31') {
              return weekPayload(
                weekStart: '2026-08-31',
                isCurrentWeek: false,
                todayDate: '2026-09-10',
              );
            }
            if (weekStart == '2026-09-14') {
              return weekPayload(
                weekStart: '2026-09-14',
                isCurrentWeek: false,
                todayDate: '2026-09-10',
              );
            }
            return weekPayload();
          },
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(requested, [null]);
    expect(find.text('7–13 сентября'), findsOneWidget);

    await tester.tap(find.byKey(const Key('week_nav_prev')));
    await tester.pumpAndSettle();
    expect(requested.last, '2026-08-31');
    expect(find.text('31 августа – 6 сентября'), findsOneWidget);
    expect(find.byKey(const Key('week_nav_current')), findsOneWidget);

    await tester.tap(find.byKey(const Key('week_nav_current')));
    await tester.pumpAndSettle();
    expect(requested.last, isNull);

    await tester.tap(find.byKey(const Key('week_nav_next')));
    await tester.pumpAndSettle();
    expect(requested.last, '2026-09-14');
  });

  testWidgets('tap event opens Object Detail with Object.id', (tester) async {
    String? openedId;
    final mock = MockClient((request) async {
      if (request.url.path == '/week') {
        return jsonOk(
          weekPayload(
            eventsByDate: {
              '2026-09-07': [
                secretaryObjectJson(
                  id: 'evt-42',
                  title: 'Office',
                  startAt: '2026-09-07T10:00:00+02:00',
                  dueAt: '2026-09-07T11:00:00+02:00',
                ),
              ],
            },
          ),
        );
      }
      if (request.url.path == '/labels/by-objects' ||
          request.url.path == '/object-bookmarks/by-objects') {
        return jsonOk({'objects': {}});
      }
      if (request.url.path == '/objects/evt-42') {
        openedId = 'evt-42';
        return jsonOk(
          secretaryObjectJson(
            id: 'evt-42',
            title: 'Office',
            startAt: '2026-09-07T10:00:00+02:00',
            dueAt: '2026-09-07T11:00:00+02:00',
            includeAllDay: false,
          ),
        );
      }
      if (request.url.path == '/objects/evt-42/neighbors') {
        return jsonOk({'object_id': 'evt-42', 'neighbors': []});
      }
      if (request.url.path == '/objects/evt-42/context') {
        return jsonOk({
          'object': secretaryObjectJson(
            id: 'evt-42',
            title: 'Office',
            startAt: '2026-09-07T10:00:00+02:00',
            dueAt: '2026-09-07T11:00:00+02:00',
            includeAllDay: false,
          ),
          'edges': [],
          'neighbors': [],
        });
      }
      return http.Response('{}', 404);
    });
    await tester.pumpWidget(buildWeek(mock));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Office'));
    await tester.pumpAndSettle();
    expect(openedId, 'evt-42');
    expect(find.byType(ObjectDetailScreen), findsOneWidget);
    expect(find.text('Использовать как контекст задачи'), findsOneWidget);
  });

  testWidgets('Week API error shows retry and Today stays usable',
      (tester) async {
    var weekShouldFail = true;
    var todayCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path == '/today') {
        todayCalls += 1;
        return jsonOk(todayPayload());
      }
      if (request.url.path == '/week') {
        if (weekShouldFail) {
          return http.Response('{"detail":"boom"}', 500);
        }
        return jsonOk(weekPayload());
      }
      if (request.url.path == '/labels/by-objects' ||
          request.url.path == '/object-bookmarks/by-objects') {
        return jsonOk({'objects': {}});
      }
      return http.Response('{}', 404);
    });
    await tester.pumpWidget(buildTemporal(mock));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Неделя'));
    await tester.pumpAndSettle();
    expect(find.text('Повторить'), findsOneWidget);

    await tester.tap(find.text('Сегодня').last);
    await tester.pumpAndSettle();
    expect(find.text('Due today'), findsOneWidget);
    expect(todayCalls, 1);

    await tester.tap(find.text('Неделя'));
    await tester.pumpAndSettle();
    weekShouldFail = false;
    await tester.tap(find.text('Повторить'));
    await tester.pumpAndSettle();
    expect(find.text('На этой неделе событий нет'), findsOneWidget);
  });

  for (final size in const [
    Size(360, 760),
    Size(800, 1280),
    Size(1280, 768),
  ]) {
    testWidgets('week agenda does not overflow at ${size.width}x${size.height}',
        (tester) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final long =
          'Очень длинное название встречи которое должно сокращаться без горизонтального переполнения';
      await tester.pumpWidget(
        buildWeek(
          weekClient(
            week: (_) => weekPayload(
              eventsByDate: {
                '2026-09-07': [
                  secretaryObjectJson(
                    id: 'long-google',
                    title: long,
                    startAt: '2026-09-07T10:00:00+02:00',
                    dueAt: '2026-09-07T11:00:00+02:00',
                  ),
                  secretaryObjectJson(
                    id: 'long-yandex',
                    title: '$long Яндекс',
                    provider: 'yandex_calendar',
                    startAt: '2026-09-07T11:00:00+02:00',
                    dueAt: '2026-09-07T12:00:00+02:00',
                  ),
                ],
              },
            ),
          ),
          size: size,
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.textContaining('Очень длинное'), findsWidgets);
    });
  }

  testWidgets('week agenda respects enlarged text scale', (tester) async {
    tester.view.physicalSize = const Size(360, 760);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final pair = controllers(
      weekClient(
        week: (_) => weekPayload(
          eventsByDate: {
            '2026-09-07': [
              secretaryObjectJson(
                id: 'scaled',
                title: 'Масштабируемая встреча',
                startAt: '2026-09-07T10:00:00+02:00',
                dueAt: '2026-09-07T11:00:00+02:00',
              ),
            ],
          },
        ),
      ),
    );
    await tester.pumpWidget(
      harness(
        size: const Size(360, 760),
        textScaler: const TextScaler.linear(1.3),
        child: WeekScreen(
          apiClient: pair.$1.apiClient,
          authController: pair.$1,
          captureController: pair.$2,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('Масштабируемая встреча'), findsOneWidget);
  });
}