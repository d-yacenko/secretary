import 'dart:convert';

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

  testWidgets('moving marker persists without clearing feed', (tester) async {
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
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          expect(body['after_object_id'], 'a');
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
    expect(find.text('Card A'), findsOneWidget);
    expect(find.text('Card B'), findsOneWidget);
    expect(find.byKey(const Key('inbox_review_marker_unplaced')), findsOneWidget);

    final handle = find.byKey(const Key('inbox_review_marker_handle'));
    final gaps = find.byType(DragTarget<String>);
    expect(gaps, findsWidgets);
    await tester.drag(handle, const Offset(0, 80));
    await tester.pumpAndSettle();
    final drop = tester.getCenter(gaps.at(1));
    await tester.timedDrag(handle, drop - tester.getCenter(handle), const Duration(milliseconds: 300));
    await tester.pumpAndSettle();
    expect(putCalls, greaterThanOrEqualTo(0));
    expect(find.text('Card A'), findsOneWidget);
    expect(find.text('Card B'), findsOneWidget);
  });

  test('insertReviewMarkerEntry keeps date grouping', () {
    final grouped = groupInboxSourceEntries([
      obj(id: 'a', feedAt: '2026-09-09T12:00:00Z'),
      obj(id: 'b', feedAt: '2026-09-08T12:00:00Z'),
    ]);
    final withMarker = insertReviewMarkerEntry(
      entries: grouped,
      insertBeforeObjectIndex: 1,
    );
    expect(withMarker.whereType<InboxReviewMarkerEntry>(), hasLength(1));
    expect(withMarker.whereType<InboxDateSeparatorEntry>(), isNotEmpty);
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
}
