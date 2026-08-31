import 'dart:async';

import '../api/api_models.dart';
import '../api/secretary_api_client.dart';

/// Result of a bounded source-sync refresh cycle.
class SourceRefreshResult {
  SourceRefreshResult({
    required this.timedOut,
    required this.statuses,
  });

  final bool timedOut;
  final List<SourceSyncStatusOut> statuses;

  bool get hasErrors => statuses.any((row) => row.status == 'error');
}

/// Triggers `POST /sources/sync` and polls `/sources/status` until settled or timeout.
class SourceRefreshService {
  SourceRefreshService({required SecretaryApiClient apiClient})
      : _apiClient = apiClient;

  final SecretaryApiClient _apiClient;

  static const Duration defaultTimeout = Duration(seconds: 12);
  static const Duration pollInterval = Duration(milliseconds: 500);

  Future<SourceRefreshResult> refreshSources({
    Duration timeout = defaultTimeout,
  }) async {
    await _apiClient.triggerSourceSync();
    final deadline = DateTime.now().add(timeout);
    List<SourceSyncStatusOut> statuses = [];
    while (DateTime.now().isBefore(deadline)) {
      statuses = await _apiClient.getSourceStatus();
      if (statuses.every(_isSettled)) {
        return SourceRefreshResult(timedOut: false, statuses: statuses);
      }
      await Future.delayed(pollInterval);
    }
    statuses = await _apiClient.getSourceStatus();
    return SourceRefreshResult(timedOut: true, statuses: statuses);
  }

  bool _isSettled(SourceSyncStatusOut row) {
    if (row.status == 'syncing') {
      return false;
    }
    if (row.status == 'error' || row.status == 'scheduled') {
      return true;
    }
    if (row.status == 'pending') {
      final nextSync = row.nextSyncAt == null
          ? null
          : DateTime.tryParse(row.nextSyncAt!);
      if (nextSync != null && nextSync.isAfter(DateTime.now())) {
        return true;
      }
      return false;
    }
    return true;
  }
}
