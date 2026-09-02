import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/sources/source_sync_error_presentation.dart';

void main() {
  const leakMarker = 'sk-testPhase28bDLeakMarker';

  SourceSyncStatusOut errorRow({
    String provider = 'gmail',
    String accountLabel = 'user@example.com',
    String? lastError,
    String? lastSuccessAt,
    String? lastAttemptAt,
  }) {
    return SourceSyncStatusOut.fromJson({
      'source': provider,
      'provider': provider,
      'account_id': '550e8400-e29b-41d4-a716-446655440000',
      'account_label': accountLabel,
      'status': 'error',
      'last_success_at': lastSuccessAt,
      'last_attempt_at': lastAttemptAt,
      'next_sync_at': null,
      'last_error': lastError,
    });
  }

  test('provider labels use friendly names', () {
    expect(sourceSyncProviderLabel('gmail'), 'Gmail');
    expect(sourceSyncProviderLabel('google_calendar'), 'Google Calendar');
    expect(sourceSyncProviderLabel('yandex_mail'), 'Yandex Mail');
    expect(sourceSyncProviderLabel('yandex_calendar'), 'Yandex Calendar');
    expect(sourceSyncProviderLabel('mattermost'), 'Mattermost');
  });

  test('safe error reason hides secret markers', () {
    final row = errorRow(lastError: leakMarker);
    expect(sourceSyncSafeErrorReason(row), isNot(contains(leakMarker)));
    expect(
        sourceSyncSafeErrorReason(row), 'Не удалось синхронизировать источник');
  });

  test('safe error reason shows sanitized backend message', () {
    final row = errorRow(lastError: 'RuntimeError');
    expect(sourceSyncSafeErrorReason(row), 'RuntimeError');
  });

  test('headline includes account label when useful', () {
    final row = errorRow();
    expect(sourceSyncErrorHeadline(row), 'Gmail — user@example.com');
  });

  test('headline omits raw account uuid', () {
    final row = errorRow(
      accountLabel: '550e8400-e29b-41d4-a716-446655440000',
    );
    expect(sourceSyncErrorHeadline(row), 'Gmail');
  });

  test('sourceSyncErrorRows filters non-error statuses', () {
    final rows = [
      errorRow(),
      SourceSyncStatusOut.fromJson({
        'source': 'google_calendar',
        'provider': 'google_calendar',
        'account_id': '1',
        'account_label': 'user@example.com',
        'status': 'scheduled',
        'last_success_at': null,
        'last_attempt_at': null,
        'next_sync_at': '2026-09-02T12:00:00Z',
        'last_error': null,
      }),
    ];
    expect(sourceSyncErrorRows(rows).length, 1);
  });
}
