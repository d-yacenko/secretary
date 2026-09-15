import 'dart:convert';

import 'package:flutter/foundation.dart';
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
import 'package:personal_secretary/inbox/inbox_conversation_groups.dart';
import 'package:personal_secretary/inbox/inbox_screen.dart';
import 'package:personal_secretary/inbox/inbox_swipe_to_remove.dart';
import 'package:personal_secretary/ui/inbox_date_groups.dart';
import 'package:shared_preferences/shared_preferences.dart';

InboxSourceObjectOut source({
  required String id,
  required String title,
  String kind = 'chat_message',
  String provider = 'telegram',
  required String feedAt,
}) {
  return InboxSourceObjectOut(
    id: id,
    title: title,
    kind: kind,
    provider: provider,
    origin: 'source',
    state: 'observed',
    status: null,
    primaryAt: feedAt,
    feedAt: feedAt,
    excerpt: title,
  );
}

Map<String, dynamic> sourceJson({
  required String id,
  required String title,
  String kind = 'chat_message',
  String provider = 'telegram',
  required String feedAt,
}) {
  return {
    'id': id,
    'title': title,
    'kind': kind,
    'provider': provider,
    'origin': 'source',
    'state': 'observed',
    'status': null,
    'primary_at': feedAt,
    'feed_at': feedAt,
    'excerpt': title,
  };
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('overlay builds a stack and keeps singleton layout', () {
    final objects = [
      source(id: 't2', title: 'two', feedAt: '2026-09-15T16:07:00Z'),
      source(id: 't1', title: 'one', feedAt: '2026-09-15T16:06:00Z'),
      source(
        id: 'ev',
        title: 'Meet',
        kind: 'event',
        provider: 'google_calendar',
        feedAt: '2026-09-15T16:05:00Z',
      ),
    ];
    final overlay = [
      InboxConversationGroup.fromJson({
        'type': 'stack',
        'stack': {
          'stack_id': 'stack-1',
          'fingerprint': 'stack-1',
          'object_ids': ['t1', 't2'],
          'display_object_ids': ['t2', 't1'],
          'provider': 'telegram',
          'conversation_key': 'telegram:_:chat:1',
          'conversation_label': 'BrainTor',
          'participants': ['BrainTor'],
          'message_count': 2,
          'start_at': '2026-09-15T16:06:00Z',
          'end_at': '2026-09-15T16:07:00Z',
          'summary': 'Обсуждали новую модель Fable.',
          'fallback_summary': 'Telegram, BrainTor, 2 сообщений, 16:06–16:07.',
          'summary_status': 'current',
        },
      }),
      InboxConversationGroup.fromJson({'type': 'singleton', 'object_id': 'ev'}),
    ];
    final entries = overlayInboxConversationEntries(objects, overlay);
    final stacks = entries.whereType<InboxConversationStackEntry>().toList();
    final singles = entries.whereType<InboxSourceObjectEntry>().toList();
    expect(stacks, hasLength(1));
    expect(stacks.first.stack.messageCount, 2);
    expect(stacks.first.children.map((e) => e.id).toList(), ['t1', 't2']);
    expect(singles.single.sourceObject.id, 'ev');
  });

  test('marker insert is outside collapsed stack coverage', () {
    final objects = [
      source(id: 'n2', title: 'new2', feedAt: '2026-09-15T16:07:00Z'),
      source(id: 'n1', title: 'new1', feedAt: '2026-09-15T16:06:00Z'),
      source(id: 'old', title: 'old', feedAt: '2026-09-15T15:00:00Z'),
    ];
    final overlay = [
      InboxConversationGroup.fromJson({
        'type': 'stack',
        'stack': {
          'stack_id': 'new-stack',
          'fingerprint': 'new-stack',
          'object_ids': ['n1', 'n2'],
          'display_object_ids': ['n2', 'n1'],
          'provider': 'telegram',
          'conversation_key': 'k',
          'conversation_label': 'BrainTor',
          'participants': ['BrainTor'],
          'message_count': 2,
          'start_at': '2026-09-15T16:06:00Z',
          'end_at': '2026-09-15T16:07:00Z',
          'fallback_summary': 'Telegram, BrainTor, 2 сообщений, 16:06–16:07.',
          'summary_status': 'fallback',
        },
      }),
      InboxConversationGroup.fromJson({'type': 'singleton', 'object_id': 'old'}),
    ];
    final grouped = overlayInboxConversationEntries(objects, overlay);
    final withMarker = insertReviewMarkerAcrossStacks(
      entries: grouped,
      insertBeforeObjectIndex: 2,
    );
    expect(withMarker.whereType<InboxReviewMarkerEntry>(), hasLength(1));
    final markerAt = withMarker.indexWhere((e) => e is InboxReviewMarkerEntry);
    expect(withMarker[markerAt - 1], isA<InboxConversationStackEntry>());
    expect(withMarker[markerAt + 1], isA<InboxSourceObjectEntry>());
  });

  testWidgets('collapsed stack expands original rows and does not swipe-delete the stack',
      (tester) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    tester.view.physicalSize = const Size(360, 760);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      debugDefaultTargetPlatformOverride = null;
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    final inbox = {
      'unresolved_notifications': <Object>[],
      'recent_source_objects': [
        sourceJson(id: 't2', title: 'two', feedAt: '2026-09-15T16:07:00Z'),
        sourceJson(id: 't1', title: 'one', feedAt: '2026-09-15T16:06:00Z'),
        sourceJson(
          id: 'solo',
          title: 'singleton mail',
          kind: 'email',
          provider: 'gmail',
          feedAt: '2026-09-15T15:00:00Z',
        ),
      ],
      'source_sync_status': <Object>[],
      'conversation_groups': [
        {
          'type': 'stack',
          'stack': {
            'stack_id': 'stack-ui',
            'fingerprint': 'stack-ui',
            'object_ids': ['t1', 't2'],
            'display_object_ids': ['t2', 't1'],
            'provider': 'telegram',
            'conversation_key': 'k',
            'conversation_label': 'BrainTor',
            'participants': ['BrainTor'],
            'message_count': 2,
            'start_at': '2026-09-15T16:06:00Z',
            'end_at': '2026-09-15T16:07:00Z',
            'summary': 'Обсуждали новую модель Fable.',
            'fallback_summary': 'Telegram, BrainTor, 2 сообщений, 16:06–16:07.',
            'summary_status': 'current',
          },
        },
        {'type': 'singleton', 'object_id': 'solo'},
      ],
    };

    final apiClient = SecretaryApiClient(
      httpClient: MockClient((request) async {
        if (request.url.path == '/inbox') {
          return http.Response.bytes(
            utf8.encode(jsonEncode(inbox)),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'},
          );
        }
        if (request.url.path.endsWith('/labels/by-objects') ||
            request.url.path.endsWith('/object-bookmarks/by-objects')) {
          return http.Response.bytes(
            utf8.encode(jsonEncode({'objects': <String, Object>{}})),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'},
          );
        }
        return http.Response('{}', 404);
      }),
    );
    apiClient.configure(baseUrl: 'https://secretary.example', token: 't');
    final auth = AuthController(
      apiClient: apiClient,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    final capture = CaptureController(apiClient: apiClient, authController: auth);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: InboxScreen(
            apiClient: apiClient,
            authController: auth,
            captureController: capture,
            passiveRefreshInterval: const Duration(days: 1),
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.byKey(const Key('inbox_conversation_stack_stack-ui')), findsOneWidget);
    expect(find.text('Обсуждали новую модель Fable.'), findsOneWidget);
    expect(find.textContaining('2 сообщений'), findsOneWidget);
    expect(find.text('BrainTor · Telegram'), findsOneWidget);
    expect(find.text('two'), findsNothing);
    expect(find.text('singleton mail'), findsWidgets);

    final stackSwipes = find.descendant(
      of: find.byKey(const Key('inbox_conversation_stack_stack-ui')),
      matching: find.byType(InboxSwipeToRemove),
    );
    expect(stackSwipes, findsNothing);

    await tester.tap(find.byKey(const Key('inbox_conversation_stack_stack-ui')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.text('one'), findsWidgets);
    expect(find.text('two'), findsWidgets);
    expect(find.byType(InboxSwipeToRemove), findsWidgets);
    debugDefaultTargetPlatformOverride = null;
  });
}
