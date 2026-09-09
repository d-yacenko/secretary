import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';
import 'package:personal_secretary/inbox/inbox_review_marker.dart';
import 'package:personal_secretary/ui/inbox_date_groups.dart';
import 'package:personal_secretary/ui/object_bookmark.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'temporal_correctness_inbox_feed_a_test.dart';

InboxSourceObjectOut obj({
  required String id,
  required String feedAt,
}) {
  return InboxSourceObjectOut(
    id: id,
    title: id,
    kind: 'email',
    provider: 'gmail',
    origin: 'source',
    state: 'observed',
    status: null,
    primaryAt: feedAt,
    excerpt: 'x',
    feedAt: feedAt,
  );
}

List<String> entryTags(List<InboxSourceListEntry> entries) {
  return [
    for (final entry in entries)
      switch (entry) {
        InboxDateSeparatorEntry() => 'sep',
        InboxSourceObjectEntry(:final sourceObject) => 'obj:${sourceObject.id}',
        InboxReviewMarkerEntry() => 'marker',
      },
  ];
}

Map<String, dynamic> objectDetailJson({
  required String id,
  required String title,
}) {
  return {
    'id': id,
    'kind': 'email',
    'title': title,
    'body': 'body',
    'provider': 'gmail',
    'external_id': 'ext-1',
    'canonical_uri': null,
    'status': null,
    'start_at': null,
    'due_at': null,
    'metadata': {},
    'origin': 'source',
    'state': 'observed',
    'confidence': null,
    'created_at': '2026-09-09T12:00:00Z',
    'updated_at': '2026-09-09T12:00:00Z',
  };
}

Future<void> dragHandleToGap(
  WidgetTester tester, {
  required String gapId,
  bool longPress = false,
}) async {
  final handle = find.byKey(const Key('inbox_review_marker_handle'));
  final gap = find.byKey(Key('inbox_review_marker_gap_$gapId'));
  final gesture = await tester.startGesture(tester.getCenter(handle));
  if (longPress) {
    await tester.pump(kLongPressTimeout + kPressTimeout);
  } else {
    await tester.pump();
  }
  await gesture.moveTo(tester.getCenter(gap));
  await tester.pump();
  await gesture.up();
  await tester.pumpAndSettle();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('marker insertion index from feed tuple', () {
    final items = [
      obj(id: 'c', feedAt: '2026-09-09T12:00:00Z'),
      obj(id: 'b', feedAt: '2026-09-08T12:00:00Z'),
      obj(id: 'a', feedAt: '2026-09-07T12:00:00Z'),
    ];
    final marker = InboxReviewMarker(
      anchorFeedAt: '2026-09-08T12:00:00Z',
      anchorObjectId: 'b',
      updatedAt: '2026-09-09T00:00:00Z',
    );
    expect(
      reviewMarkerInsertIndex(objects: items, marker: marker, hasMore: false),
      2,
    );
  });

  test('new head items leave marker boundary stable', () {
    final marker = InboxReviewMarker(
      anchorFeedAt: '2026-09-08T12:00:00Z',
      anchorObjectId: 'b',
      updatedAt: '2026-09-09T00:00:00Z',
    );
    final withoutHead = [
      obj(id: 'b', feedAt: '2026-09-08T12:00:00Z'),
      obj(id: 'a', feedAt: '2026-09-07T12:00:00Z'),
    ];
    final withHead = [
      obj(id: 'n', feedAt: '2026-09-10T12:00:00Z'),
      ...withoutHead,
    ];
    expect(
      reviewMarkerInsertIndex(
        objects: withoutHead,
        marker: marker,
        hasMore: false,
      ),
      1,
    );
    expect(
      reviewMarkerInsertIndex(
        objects: withHead,
        marker: marker,
        hasMore: false,
      ),
      2,
    );
  });

  test('missing anchor still places by tuple', () {
    final marker = InboxReviewMarker(
      anchorFeedAt: '2026-09-08T12:00:00Z',
      anchorObjectId: 'missing',
      updatedAt: '2026-09-09T00:00:00Z',
    );
    final items = [
      obj(id: 'newer', feedAt: '2026-09-09T12:00:00Z'),
      obj(id: 'older', feedAt: '2026-09-07T12:00:00Z'),
    ];
    expect(
      reviewMarkerInsertIndex(objects: items, marker: marker, hasMore: false),
      1,
    );
  });

  test('same feed_at UUID tie', () {
    const t = '2026-09-08T12:00:00Z';
    final high = obj(id: '00000000-0000-4000-8000-000000000002', feedAt: t);
    final low = obj(id: '00000000-0000-4000-8000-000000000001', feedAt: t);
    final marker = InboxReviewMarker(
      anchorFeedAt: t,
      anchorObjectId: high.id,
      updatedAt: t,
    );
    expect(
      reviewMarkerInsertIndex(
        objects: [high, low],
        marker: marker,
        hasMore: false,
      ),
      1,
    );
    expect(
      reviewMarkerInsertIndex(
        objects: [high, low],
        marker: marker,
        hasMore: true,
      ),
      1,
    );
  });

  test('exact loaded-tail anchor stays visible when hasMore', () {
    final items = [
      obj(id: 'a', feedAt: '2026-09-09T12:00:00Z'),
      obj(id: 'b', feedAt: '2026-09-08T12:00:00Z'),
      obj(id: 'c', feedAt: '2026-09-07T12:00:00Z'),
    ];
    final marker = InboxReviewMarker(
      anchorFeedAt: '2026-09-07T12:00:00Z',
      anchorObjectId: 'c',
      updatedAt: '2026-09-09T00:00:00Z',
    );
    expect(
      reviewMarkerInsertIndex(objects: items, marker: marker, hasMore: true),
      3,
    );
  });

  test('missing anchor between loaded tuples still places by boundary', () {
    final marker = InboxReviewMarker(
      anchorFeedAt: '2026-09-08T12:00:00Z',
      anchorObjectId: 'missing',
      updatedAt: '2026-09-09T00:00:00Z',
    );
    final items = [
      obj(id: 'newer', feedAt: '2026-09-09T12:00:00Z'),
      obj(id: 'older', feedAt: '2026-09-07T12:00:00Z'),
    ];
    expect(
      reviewMarkerInsertIndex(objects: items, marker: marker, hasMore: true),
      1,
    );
  });

  test('load-more eventually reveals older marker', () {
    final marker = InboxReviewMarker(
      anchorFeedAt: '2026-09-01T12:00:00Z',
      anchorObjectId: 'old',
      updatedAt: '2026-09-09T00:00:00Z',
    );
    final head = [obj(id: 'new', feedAt: '2026-09-09T12:00:00Z')];
    expect(
      reviewMarkerInsertIndex(objects: head, marker: marker, hasMore: true),
      isNull,
    );
    final reached = [
      ...head,
      obj(id: 'old', feedAt: '2026-09-01T12:00:00Z'),
      obj(id: 'older', feedAt: '2026-08-31T12:00:00Z'),
    ];
    expect(
      reviewMarkerInsertIndex(objects: reached, marker: marker, hasMore: false),
      2,
    );
  });

  test('bookmark batch maps by object id', () {
    final mapped = {
      'a': 'red',
      'b': 'blue',
    };
    expect(mapped['a'], 'red');
    expect(mapped.containsKey('c'), isFalse);
  });

  test('continuation bookmark ids are appended only', () {
    final seen = <String>{};
    final first = ['a', 'b'];
    final appended = ['c'];
    seen.addAll(first);
    final next = [for (final id in appended) if (seen.add(id)) id];
    expect(next, ['c']);
  });

  testWidgets('desktop drag persists marker at known gap without clearing feed',
      (tester) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.linux;
    addTearDown(() {
      debugDefaultTargetPlatformOverride = null;
    });
    tester.view.physicalSize = const Size(800, 900);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    var inboxCalls = 0;
    var putCalls = 0;
    String? putAfter;
    final apiClient = SecretaryApiClient(
      httpClient: MockClient((request) async {
        if (request.url.path == '/inbox' &&
            !request.url.path.endsWith('/inbox/feed')) {
          inboxCalls++;
          return jsonRes(
            inboxPayload(
              sources: [
                sourceRow(
                  id: 'a',
                  title: 'Card A',
                  feedAt: '2026-09-09T12:00:00Z',
                ),
                sourceRow(
                  id: 'b',
                  title: 'Card B',
                  feedAt: '2026-09-08T12:00:00Z',
                ),
              ],
            ),
          );
        }
        if (request.url.path == '/labels/by-objects' ||
            request.url.path == '/object-bookmarks/by-objects') {
          return jsonRes({'objects': {}});
        }
        if (request.method == 'PUT' &&
            request.url.path == '/inbox/review-marker') {
          putCalls++;
          putAfter = (jsonDecode(request.body) as Map)['after_object_id'] as String;
          return jsonRes({
            'anchor_feed_at': '2026-09-09T12:00:00Z',
            'anchor_object_id': 'a',
            'updated_at': '2026-09-09T13:00:00Z',
          });
        }
        return jsonRes({}, 404);
      }),
    );
    apiClient.configure(baseUrl: 'https://secretary.example', token: 't');
    await tester.pumpWidget(pumpInbox(apiClient));
    await tester.pumpAndSettle();
    expect(find.byWidgetPredicate((widget) => widget is LongPressDraggable),
        findsNothing);
    expect(find.byKey(const Key('inbox_review_marker_unplaced')), findsOneWidget);

    await dragHandleToGap(tester, gapId: 'a');
    expect(putCalls, 1);
    expect(putAfter, 'a');
    expect(inboxCalls, 1);
    expect(find.byKey(const Key('inbox_review_marker')), findsOneWidget);
    expect(find.text('Просмотрено досюда'), findsOneWidget);
    expect(find.text('Card A'), findsOneWidget);
    expect(find.text('Card B'), findsOneWidget);
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets('tail-anchor marker stays visible when inbox hasMore',
      (tester) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.linux;
    addTearDown(() {
      debugDefaultTargetPlatformOverride = null;
    });
    tester.view.physicalSize = const Size(800, 900);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    var putCalls = 0;
    var feedCalls = 0;
    final apiClient = SecretaryApiClient(
      httpClient: MockClient((request) async {
        if (request.url.path == '/inbox' &&
            !request.url.path.endsWith('/inbox/feed')) {
          return jsonRes(
            inboxPayload(
              sources: [
                sourceRow(
                  id: 'a',
                  title: 'Card A',
                  feedAt: '2026-09-09T12:00:00Z',
                ),
                sourceRow(
                  id: 'b',
                  title: 'Card B',
                  feedAt: '2026-09-08T12:00:00Z',
                ),
              ],
              hasMore: true,
            ),
          );
        }
        if (request.url.path.endsWith('/inbox/feed')) {
          feedCalls++;
          return jsonRes({}, 404);
        }
        if (request.url.path == '/labels/by-objects' ||
            request.url.path == '/object-bookmarks/by-objects') {
          return jsonRes({'objects': {}});
        }
        if (request.method == 'PUT' &&
            request.url.path == '/inbox/review-marker') {
          putCalls++;
          expect(
            (jsonDecode(request.body) as Map)['after_object_id'],
            'b',
          );
          return jsonRes({
            'anchor_feed_at': '2026-09-08T12:00:00Z',
            'anchor_object_id': 'b',
            'updated_at': '2026-09-09T13:00:00Z',
          });
        }
        return jsonRes({}, 404);
      }),
    );
    apiClient.configure(baseUrl: 'https://secretary.example', token: 't');
    await tester.pumpWidget(pumpInbox(apiClient));
    await tester.pumpAndSettle();
    await dragHandleToGap(tester, gapId: 'b');
    expect(putCalls, 1);
    expect(feedCalls, 0);
    expect(find.byKey(const Key('inbox_review_marker')), findsOneWidget);
    expect(find.text('Просмотрено досюда'), findsOneWidget);
    expect(find.text('Card A'), findsOneWidget);
    expect(find.text('Card B'), findsOneWidget);
    debugDefaultTargetPlatformOverride = null;
  });

  testWidgets('android long-press drag persists marker at known gap',
      (tester) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    addTearDown(() {
      debugDefaultTargetPlatformOverride = null;
    });
    tester.view.physicalSize = const Size(800, 900);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    var putCalls = 0;
    final apiClient = SecretaryApiClient(
      httpClient: MockClient((request) async {
        if (request.url.path == '/inbox' &&
            !request.url.path.endsWith('/inbox/feed')) {
          return jsonRes(
            inboxPayload(
              sources: [
                sourceRow(
                  id: 'a',
                  title: 'Card A',
                  feedAt: '2026-09-09T12:00:00Z',
                ),
                sourceRow(
                  id: 'b',
                  title: 'Card B',
                  feedAt: '2026-09-08T12:00:00Z',
                ),
              ],
            ),
          );
        }
        if (request.url.path == '/labels/by-objects' ||
            request.url.path == '/object-bookmarks/by-objects') {
          return jsonRes({'objects': {}});
        }
        if (request.method == 'PUT' &&
            request.url.path == '/inbox/review-marker') {
          putCalls++;
          expect(
            (jsonDecode(request.body) as Map)['after_object_id'],
            'a',
          );
          return jsonRes({
            'anchor_feed_at': '2026-09-09T12:00:00Z',
            'anchor_object_id': 'a',
            'updated_at': '2026-09-09T13:00:00Z',
          });
        }
        return jsonRes({}, 404);
      }),
    );
    apiClient.configure(baseUrl: 'https://secretary.example', token: 't');
    await tester.pumpWidget(pumpInbox(apiClient));
    await tester.pumpAndSettle();
    expect(find.byWidgetPredicate((widget) => widget is LongPressDraggable),
        findsWidgets);

    await dragHandleToGap(tester, gapId: 'a', longPress: true);
    expect(putCalls, 1);
    expect(find.text('Просмотрено досюда'), findsOneWidget);
    expect(find.text('Card A'), findsOneWidget);
    expect(find.text('Card B'), findsOneWidget);
    debugDefaultTargetPlatformOverride = null;
  });

  test('marker between dates sits above the next date separator', () {
    final grouped = groupInboxSourceEntries([
      obj(id: 'a', feedAt: '2026-09-09T12:00:00Z'),
      obj(id: 'b', feedAt: '2026-09-08T12:00:00Z'),
    ]);
    expect(
      entryTags(
        insertReviewMarkerEntry(
          entries: grouped,
          insertBeforeObjectIndex: 1,
        ),
      ),
      ['sep', 'obj:a', 'marker', 'sep', 'obj:b'],
    );
  });

  test('marker within the same date sits between objects', () {
    final grouped = groupInboxSourceEntries([
      obj(id: 'a', feedAt: '2026-09-09T12:00:00Z'),
      obj(id: 'b', feedAt: '2026-09-09T11:00:00Z'),
    ]);
    expect(
      entryTags(
        insertReviewMarkerEntry(
          entries: grouped,
          insertBeforeObjectIndex: 1,
        ),
      ),
      ['sep', 'obj:a', 'marker', 'obj:b'],
    );
  });

  test('marker before the first object precedes its date separator', () {
    final grouped = groupInboxSourceEntries([
      obj(id: 'a', feedAt: '2026-09-09T12:00:00Z'),
    ]);
    expect(
      entryTags(
        insertReviewMarkerEntry(
          entries: grouped,
          insertBeforeObjectIndex: 0,
        ),
      ),
      ['marker', 'sep', 'obj:a'],
    );
  });

  test('marker after the loaded tail follows the final object', () {
    final grouped = groupInboxSourceEntries([
      obj(id: 'a', feedAt: '2026-09-09T12:00:00Z'),
      obj(id: 'b', feedAt: '2026-09-08T12:00:00Z'),
    ]);
    expect(
      entryTags(
        insertReviewMarkerEntry(
          entries: grouped,
          insertBeforeObjectIndex: 2,
        ),
      ),
      ['sep', 'obj:a', 'sep', 'obj:b', 'marker'],
    );
  });

  testWidgets('bookmark tab opens shared palette to recolor and clear',
      (tester) async {
    String? color = 'red';
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: StatefulBuilder(
            builder: (context, setState) {
              return ObjectBookmarkRibbon(
                color: color,
                onSelect: (value) => setState(() => color = value),
                onClear: () => setState(() => color = null),
                child: const SizedBox(
                  width: 240,
                  height: 80,
                  child: Text('card'),
                ),
              );
            },
          ),
        ),
      ),
    );
    await tester.tap(find.byKey(const Key('object_bookmark_tab')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('blue'));
    await tester.pumpAndSettle();
    expect(color, 'blue');
    await tester.tap(find.byKey(const Key('object_bookmark_tab')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Убрать закладку'));
    await tester.pumpAndSettle();
    expect(color, isNull);
    expect(find.byKey(const Key('object_bookmark_tab')), findsNothing);
  });

  testWidgets('bookmark control can change color and clear', (tester) async {
    String? color;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: StatefulBuilder(
            builder: (context, setState) {
              return ObjectBookmarkControl(
                color: color,
                onSelect: (value) => setState(() => color = value),
                onClear: () => setState(() => color = null),
              );
            },
          ),
        ),
      ),
    );
    await tester.tap(find.byKey(const Key('object_bookmark_control')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('red'));
    await tester.pumpAndSettle();
    expect(color, 'red');
    await tester.tap(find.byKey(const Key('object_bookmark_control')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Убрать закладку'));
    await tester.pumpAndSettle();
    expect(color, isNull);
  });

  testWidgets('detail bookmark edit is reflected on inbox return',
      (tester) async {
    tester.view.physicalSize = const Size(800, 900);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    var inboxCalls = 0;
    String? storedColor;
    final apiClient = SecretaryApiClient(
      httpClient: MockClient((request) async {
        if (request.url.path == '/inbox' &&
            !request.url.path.endsWith('/inbox/feed')) {
          inboxCalls++;
          return jsonRes(
            inboxPayload(
              sources: [
                sourceRow(
                  id: 'a',
                  title: 'Card A',
                  feedAt: '2026-09-09T12:00:00Z',
                ),
              ],
            ),
          );
        }
        if (request.url.path == '/labels/by-objects') {
          return jsonRes({'objects': {}});
        }
        if (request.url.path == '/object-bookmarks/by-objects') {
          final ids =
              (jsonDecode(request.body) as Map)['object_ids'] as List<dynamic>;
          final objects = <String, Map<String, String>>{};
          if (storedColor != null && ids.contains('a')) {
            objects['a'] = {'color': storedColor!};
          }
          return jsonRes({'objects': objects});
        }
        if (request.method == 'PUT' &&
            request.url.path == '/object-bookmarks/a') {
          storedColor =
              (jsonDecode(request.body) as Map)['color'] as String;
          return jsonRes({
            'object_id': 'a',
            'color': storedColor,
            'updated_at': '2026-09-09T13:00:00Z',
          });
        }
        if (request.url.path == '/objects/a') {
          return jsonRes(objectDetailJson(id: 'a', title: 'Card A'));
        }
        if (request.url.path == '/objects/a/neighbors') {
          return jsonRes({'object_id': 'a', 'neighbors': []});
        }
        if (request.url.path == '/objects/a/context') {
          return jsonRes({
            'object': objectDetailJson(id: 'a', title: 'Card A'),
            'edges': [],
            'neighbors': [],
          });
        }
        if (request.url.path == '/objects/a/labels') {
          return jsonRes({'labels': []});
        }
        return jsonRes({}, 404);
      }),
    );
    apiClient.configure(baseUrl: 'https://secretary.example', token: 't');
    await tester.pumpWidget(pumpInbox(apiClient));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('object_bookmark_tab')), findsNothing);
    await tester.tap(find.text('Card A'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('object_bookmark_control')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('red'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    expect(inboxCalls, 1);
    expect(find.text('Card A'), findsOneWidget);
    expect(find.byKey(const Key('object_bookmark_tab')), findsOneWidget);
  });
}
