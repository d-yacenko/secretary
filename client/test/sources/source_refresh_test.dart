import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';
import 'package:personal_secretary/sources/source_refresh_service.dart';

void main() {
  test('refreshSources triggers sync and polls until scheduled', () async {
    var statusCalls = 0;
    final client = SecretaryApiClient(
      httpClient: MockClient((request) async {
        if (request.method == 'POST' && request.url.path.endsWith('/sources/sync')) {
          return http.Response(jsonEncode({'triggered': ['gmail:1'], 'count': 1}), 200);
        }
        if (request.url.path.endsWith('/sources/status')) {
          statusCalls += 1;
          final status = statusCalls < 2 ? 'pending' : 'scheduled';
          return http.Response(
            jsonEncode({
              'sources': [
                {
                  'source': 'gmail',
                  'provider': 'gmail',
                  'account_id': '1',
                  'account_label': 'user@example.com',
                  'status': status,
                  'last_success_at': status == 'scheduled' ? '2026-08-31T12:00:00Z' : null,
                  'last_attempt_at': null,
                  'next_sync_at': status == 'scheduled' ? '2026-08-31T12:05:00Z' : null,
                  'last_error': null,
                },
              ],
            }),
            200,
          );
        }
        return http.Response('{}', 404);
      }),
    );
    client.configure(baseUrl: 'https://secretary.example', token: 't');

    final service = SourceRefreshService(apiClient: client);
    final result = await service.refreshSources(
      timeout: const Duration(seconds: 2),
    );

    expect(result.timedOut, isFalse);
    expect(statusCalls, greaterThanOrEqualTo(2));
  });

  testWidgets('Today refresh calls sources sync', (tester) async {
    String? syncMethod;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) {
              final client = SecretaryApiClient(
                httpClient: MockClient((request) async {
                  if (request.method == 'POST' &&
                      request.url.path.endsWith('/sources/sync')) {
                    syncMethod = request.method;
                    return http.Response(
                      jsonEncode({'triggered': [], 'count': 0}),
                      200,
                    );
                  }
                  if (request.url.path.endsWith('/sources/status')) {
                    return http.Response(jsonEncode({'sources': []}), 200);
                  }
                  if (request.url.path == '/today') {
                    return http.Response(
                      jsonEncode({
                        'date': '2026-08-31',
                        'timezone': 'Europe/Moscow',
                        'day_start': '2026-08-31T00:00:00+03:00',
                        'tasks': [],
                        'calendar_events': [],
                        'notifications': [],
                      }),
                      200,
                    );
                  }
                  return http.Response('{}', 404);
                }),
              );
              client.configure(baseUrl: 'https://secretary.example', token: 't');
              final service = SourceRefreshService(apiClient: client);
              return IconButton(
                onPressed: () => service.refreshSources(
                  timeout: const Duration(milliseconds: 100),
                ),
                icon: const Icon(Icons.refresh),
              );
            },
          ),
        ),
      ),
    );

    await tester.tap(find.byIcon(Icons.refresh));
    await tester.pumpAndSettle();

    expect(syncMethod, 'POST');
  });
}
