import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/auth/token_store.dart';
import 'package:personal_secretary/capture/capture_controller.dart';
import 'package:personal_secretary/objects/object_detail_screen.dart';
import 'package:personal_secretary/today/temporal_area.dart';
import 'package:personal_secretary/today/today_screen.dart';
import 'package:personal_secretary/today/week_event_time_label.dart';
import 'package:personal_secretary/today/week_kalender_events.dart';
import 'package:personal_secretary/today/week_screen.dart';
import 'package:personal_secretary/ui/date_format.dart';

import '../test_secretary_api_client.dart';

void main() {
  const baseUrl = 'https://secretary.example';
  const token = 'week-token';
  const desktopSize = Size(1280, 768);
  DateTime testNow() => DateTime(2026, 9, 10, 10, 0);

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
    return {
      'week_start': weekStart,
      'week_end': shiftCalendarDate(weekStart, 7),
      'timezone': 'Europe/Amsterdam',
      'window_start': '${weekStart}T00:00:00+02:00',
      'window_end': '${shiftCalendarDate(weekStart, 7)}T00:00:00+02:00',
      'today_date': todayDate,
      'is_current_week': isCurrentWeek,
      'days': [
        for (var i = 0; i < 7; i++)
          {
            'date': shiftCalendarDate(weekStart, i),
            'is_today': shiftCalendarDate(weekStart, i) == todayDate,
            'events': eventsByDate[shiftCalendarDate(weekStart, i)] ??
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
    Size size = desktopSize,
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
    final apiClient = testSecretaryApiClient(mock);
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

  Widget buildWeek(
    MockClient mock, {
    Size size = desktopSize,
    DateTime Function()? now,
  }) {
    final pair = controllers(mock);
    return harness(
      size: size,
      child: WeekScreen(
        apiClient: pair.$1.apiClient,
        authController: pair.$1,
        captureController: pair.$2,
        now: now ?? testNow,
      ),
    );
  }

  Widget buildTemporal(MockClient mock, {Size size = desktopSize}) {
    final pair = controllers(mock);
    return harness(
      size: size,
      child: TemporalArea(
        apiClient: pair.$1.apiClient,
        authController: pair.$1,
        captureController: pair.$2,
        passiveRefreshInterval: const Duration(days: 1),
        clockTick: const Duration(days: 1),
        now: testNow,
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

  Future<void> pumpCalendar(WidgetTester tester) async {
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pump(const Duration(milliseconds: 50));
  }

  test('formatWeekRange uses Monday-Sunday local dates', () {
    expect(formatWeekRange('2026-09-07'), '7–13 сентября');
    expect(formatWeekRange('2026-08-31'), '31 августа – 6 сентября');
  });

  test('calendar-date arithmetic is DST-safe around fall-back', () {
    expect(shiftCalendarDate('2026-10-19', 7), '2026-10-26');
    expect(shiftCalendarDate('2026-10-26', -7), '2026-10-19');
    expect(addCalendarDays(parseCalendarDate('2026-10-19'), 7),
        DateTime.utc(2026, 10, 26));
    expect(parseCalendarDate('2026-10-19').isUtc, isTrue);
    expect(
      parseCalendarDate('2026-10-19').add(const Duration(days: 7)),
      DateTime.utc(2026, 10, 26),
    );
  });

  test('weekEventTimeLabel is day-local for timed spans', () {
    String iso(int year, int month, int day, int hour, int minute) {
      return DateTime(year, month, day, hour, minute).toIso8601String();
    }

    expect(
      weekEventTimeLabel(
        dayDate: '2026-09-07',
        allDay: false,
        startAt: iso(2026, 9, 7, 9, 0),
        dueAt: iso(2026, 9, 7, 10, 0),
      ),
      '09:00',
    );
    expect(
      weekEventTimeLabel(
        dayDate: '2026-09-07',
        allDay: false,
        startAt: iso(2026, 9, 7, 23, 0),
        dueAt: iso(2026, 9, 8, 1, 0),
      ),
      'с 23:00',
    );
    expect(
      weekEventTimeLabel(
        dayDate: '2026-09-08',
        allDay: false,
        startAt: iso(2026, 9, 7, 23, 0),
        dueAt: iso(2026, 9, 8, 1, 0),
      ),
      'до 01:00',
    );
    expect(
      weekEventTimeLabel(
        dayDate: '2026-09-08',
        allDay: false,
        startAt: iso(2026, 9, 7, 18, 0),
        dueAt: iso(2026, 9, 10, 10, 0),
      ),
      'Продолжается',
    );
    expect(
      weekEventTimeLabel(
        dayDate: '2026-09-09',
        allDay: false,
        startAt: iso(2026, 9, 7, 18, 0),
        dueAt: iso(2026, 9, 10, 10, 0),
      ),
      'Продолжается',
    );
    expect(
      weekEventTimeLabel(
        dayDate: '2026-09-10',
        allDay: false,
        startAt: iso(2026, 9, 7, 18, 0),
        dueAt: iso(2026, 9, 10, 10, 0),
      ),
      'до 10:00',
    );
    expect(
      weekEventTimeLabel(
        dayDate: '2026-09-07',
        allDay: true,
        startAt: iso(2026, 9, 7, 0, 0),
        dueAt: iso(2026, 9, 8, 0, 0),
      ),
      'Весь день',
    );
  });

  test('weekOutToKalenderEvents feeds each Object once with original span', () {
    String iso(int y, int m, int d, int h, int min) =>
        DateTime(y, m, d, h, min).toIso8601String();
    final overnight = secretaryObjectJson(
      id: 'overnight',
      title: 'Night shift',
      startAt: iso(2026, 9, 7, 23, 0),
      dueAt: iso(2026, 9, 8, 1, 0),
    );
    final trip = secretaryObjectJson(
      id: 'trip',
      title: 'Trip',
      startAt: iso(2026, 9, 7, 18, 0),
      dueAt: iso(2026, 9, 10, 10, 0),
    );
    final holiday = secretaryObjectJson(
      id: 'holiday',
      title: 'Holiday',
      allDay: true,
      startAt: iso(2026, 9, 7, 0, 0),
      dueAt: iso(2026, 9, 8, 0, 0),
    );
    final events = weekOutToKalenderEvents(
      WeekOut.fromJson(
        weekPayload(
          eventsByDate: {
            '2026-09-07': [holiday, overnight, trip],
            '2026-09-08': [overnight, trip],
            '2026-09-09': [trip],
            '2026-09-10': [trip],
          },
        ),
      ),
    );
    expect(events.map((e) => e.objectId).toSet(), {'holiday', 'overnight', 'trip'});
    expect(events.singleWhere((e) => e.objectId == 'holiday').isAllDay, isTrue);
    expect(events.singleWhere((e) => e.objectId == 'overnight').isAllDay, isFalse);
    expect(
      events.singleWhere((e) => e.objectId == 'overnight').dateTimeRange.duration,
      const Duration(hours: 2),
    );
    expect(
      events.singleWhere((e) => e.objectId == 'trip').dateTimeRange.duration,
      const Duration(hours: 64),
    );
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
    await pumpCalendar(tester);

    expect(find.byType(TodayScreen), findsOneWidget);
    expect(find.text('Due today'), findsOneWidget);
    expect(find.text('Standup'), findsOneWidget);
    expect(find.text('Неделя'), findsOneWidget);
    expect(todayCalls, 1);
    expect(weekCalls, 0);

    await tester.tap(find.text('Неделя'));
    await pumpCalendar(tester);
    expect(find.byType(WeekScreen), findsOneWidget);
    expect(find.byKey(const Key('week_time_grid')), findsOneWidget);
    expect(find.text('На этой неделе событий нет'), findsOneWidget);
    expect(weekCalls, 1);
    expect(todayCalls, 1);

    await tester.tap(find.text('Сегодня').last);
    await pumpCalendar(tester);
    expect(find.text('Due today'), findsOneWidget);
    expect(find.text('Standup'), findsOneWidget);
    expect(todayCalls, 1);
  });

  testWidgets('desktop week shows seven columns, overlap, providers, all-day',
      (tester) async {
    tester.view.physicalSize = desktopSize;
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
      buildWeek(weekClient(week: (_) => payload), size: desktopSize),
    );
    await pumpCalendar(tester);

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
        tester.getTopLeft(find.byKey(Key('week_day_${dates[i]}'))).dx,
        greaterThan(tester.getTopLeft(find.byKey(Key('week_day_${dates[i - 1]}'))).dx),
      );
    }
    expect(find.text('Пн 7 сентября'), findsOneWidget);
    expect(find.text('Вс 13 сентября'), findsOneWidget);
    expect(
      tester.getTopLeft(find.byKey(const Key('week_event_2026-09-07_all-day'))).dy,
      lessThan(tester.getTopLeft(find.byKey(const Key('week_event_2026-09-07_yandex'))).dy),
    );
    final review = tester.getRect(find.byKey(const Key('week_event_2026-09-07_google')));
    final overlap =
        tester.getRect(find.byKey(const Key('week_event_2026-09-07_google-overlap')));
    expect((review.top - overlap.top).abs(), lessThan(80));
    expect((review.left - overlap.left).abs(), greaterThan(8));
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

  testWidgets('phone week does not squeeze seven day columns', (tester) async {
    const phone = Size(360, 760);
    tester.view.physicalSize = phone;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      buildWeek(weekClient(week: (_) => weekPayload()), size: phone),
    );
    await pumpCalendar(tester);
    expect(find.text('Пн 7 сентября'), findsOneWidget);
    expect(find.text('Вс 13 сентября'), findsNothing);
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
    await pumpCalendar(tester);
    expect(requested, [null]);
    expect(find.text('7–13 сентября'), findsOneWidget);

    await tester.tap(find.byKey(const Key('week_nav_prev')));
    await pumpCalendar(tester);
    expect(requested.last, '2026-08-31');
    expect(find.text('31 августа – 6 сентября'), findsOneWidget);
    expect(find.byKey(const Key('week_nav_current')), findsOneWidget);

    await tester.tap(find.byKey(const Key('week_nav_current')));
    await pumpCalendar(tester);
    expect(requested.last, isNull);

    await tester.tap(find.byKey(const Key('week_nav_next')));
    await pumpCalendar(tester);
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
    await pumpCalendar(tester);
    await tester.ensureVisible(find.text('Office'));
    await tester.tap(find.text('Office'));
    await pumpCalendar(tester);
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
    await pumpCalendar(tester);
    await tester.tap(find.text('Неделя'));
    await pumpCalendar(tester);
    expect(find.text('Повторить'), findsOneWidget);

    await tester.tap(find.text('Сегодня').last);
    await pumpCalendar(tester);
    expect(find.text('Due today'), findsOneWidget);
    expect(todayCalls, 1);

    await tester.tap(find.text('Неделя'));
    await pumpCalendar(tester);
    weekShouldFail = false;
    await tester.tap(find.text('Повторить'));
    await pumpCalendar(tester);
    expect(find.text('На этой неделе событий нет'), findsOneWidget);
  });

  testWidgets('cross-midnight continues on the next day; multi-day is in header',
      (tester) async {
    tester.view.physicalSize = desktopSize;
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    String iso(int y, int m, int d, int h, int min) =>
        DateTime(y, m, d, h, min).toIso8601String();
    final overnight = secretaryObjectJson(
      id: 'overnight',
      title: 'Night shift',
      startAt: iso(2026, 9, 7, 23, 0),
      dueAt: iso(2026, 9, 8, 1, 0),
    );
    final trip = secretaryObjectJson(
      id: 'trip',
      title: 'Trip',
      startAt: iso(2026, 9, 7, 18, 0),
      dueAt: iso(2026, 9, 10, 10, 0),
    );
    final sameDay = secretaryObjectJson(
      id: 'office',
      title: 'Office',
      startAt: iso(2026, 9, 7, 9, 0),
      dueAt: iso(2026, 9, 7, 10, 0),
    );
    final holiday = secretaryObjectJson(
      id: 'holiday',
      title: 'Holiday',
      allDay: true,
      startAt: iso(2026, 9, 7, 0, 0),
      dueAt: iso(2026, 9, 8, 0, 0),
    );
    await tester.pumpWidget(
      buildWeek(
        weekClient(
          week: (_) => weekPayload(
            eventsByDate: {
              '2026-09-07': [holiday, sameDay, overnight, trip],
              '2026-09-08': [overnight, trip],
              '2026-09-09': [trip],
              '2026-09-10': [trip],
            },
          ),
        ),
        size: desktopSize,
        now: () => DateTime(2026, 9, 10, 0, 20),
      ),
    );
    await pumpCalendar(tester);

    expect(find.byKey(const Key('week_event_2026-09-07_holiday')), findsOneWidget);
    expect(find.text('Trip'), findsOneWidget);
    expect(find.byKey(const Key('week_event_2026-09-08_overnight')), findsOneWidget);

    final bodyScrollable = find.descendant(
      of: find.byKey(const Key('week_time_grid')),
      matching: find.byType(Scrollable),
    );
    await tester.fling(bodyScrollable.first, const Offset(0, -2500), 2000);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.byKey(const Key('week_event_2026-09-07_overnight')), findsOneWidget);
    expect(find.text('Night shift'), findsWidgets);
  });

  testWidgets('failed next/previous week retry repeats the same week_start',
      (tester) async {
    final requested = <String?>[];
    final failFor = <String>{};
    await tester.pumpWidget(
      buildWeek(
        MockClient((request) async {
          if (request.url.path == '/week') {
            final weekStart = request.url.queryParameters['week_start'];
            requested.add(weekStart);
            if (weekStart != null && failFor.contains(weekStart)) {
              return http.Response('{"detail":"boom"}', 500);
            }
            if (weekStart == '2026-08-31') {
              return jsonOk(
                weekPayload(
                  weekStart: '2026-08-31',
                  isCurrentWeek: false,
                  todayDate: '2026-09-10',
                ),
              );
            }
            if (weekStart == '2026-09-14') {
              return jsonOk(
                weekPayload(
                  weekStart: '2026-09-14',
                  isCurrentWeek: false,
                  todayDate: '2026-09-10',
                ),
              );
            }
            return jsonOk(weekPayload());
          }
          if (request.url.path == '/labels/by-objects' ||
              request.url.path == '/object-bookmarks/by-objects') {
            return jsonOk({'objects': {}});
          }
          return http.Response('{}', 404);
        }),
      ),
    );
    await pumpCalendar(tester);
    expect(requested, [null]);
    expect(find.text('7–13 сентября'), findsOneWidget);

    failFor.add('2026-09-14');
    await tester.tap(find.byKey(const Key('week_nav_next')));
    await pumpCalendar(tester);
    expect(requested.last, '2026-09-14');
    expect(find.text('Повторить'), findsOneWidget);

    await tester.tap(find.text('Повторить'));
    await pumpCalendar(tester);
    expect(requested.sublist(requested.length - 2), ['2026-09-14', '2026-09-14']);
    expect(find.text('Повторить'), findsOneWidget);

    failFor.remove('2026-09-14');
    await tester.tap(find.text('Повторить'));
    await pumpCalendar(tester);
    expect(requested.last, '2026-09-14');
    expect(find.text('14–20 сентября'), findsOneWidget);

    failFor.add('2026-09-07');
    await tester.tap(find.byKey(const Key('week_nav_prev')));
    await pumpCalendar(tester);
    expect(requested.last, '2026-09-07');
    expect(find.text('Повторить'), findsOneWidget);

    await tester.tap(find.text('Повторить'));
    await pumpCalendar(tester);
    expect(requested.last, '2026-09-07');
  });

  for (final size in const [
    Size(360, 760),
    Size(800, 1280),
    Size(1280, 768),
  ]) {
    testWidgets('week grid does not overflow at ${size.width}x${size.height}',
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
      await pumpCalendar(tester);
      expect(tester.takeException(), isNull);
      expect(find.textContaining('Очень длинное'), findsWidgets);
    });
  }

  testWidgets('week grid respects enlarged text scale', (tester) async {
    tester.view.physicalSize = desktopSize;
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
        size: desktopSize,
        textScaler: const TextScaler.linear(1.3),
        child: WeekScreen(
          apiClient: pair.$1.apiClient,
          authController: pair.$1,
          captureController: pair.$2,
          now: testNow,
        ),
      ),
    );
    await pumpCalendar(tester);
    expect(tester.takeException(), isNull);
    expect(find.text('Масштабируемая встреча'), findsOneWidget);
  });
}
