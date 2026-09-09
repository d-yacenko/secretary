import '../api/api_error.dart';
import '../api/secretary_api_client.dart';

const int kBookmarksByObjectsMax = 100;

typedef AuthFailure = void Function();

List<String> uniqueObjectIds(Iterable<String> objectIds) {
  final unique = <String>[];
  final seen = <String>{};
  for (final id in objectIds) {
    final trimmed = id.trim();
    if (trimmed.isEmpty || !seen.add(trimmed)) {
      continue;
    }
    unique.add(trimmed);
  }
  return unique;
}

Future<Map<String, String>> loadBookmarksByObjects({
  required SecretaryApiClient apiClient,
  required AuthFailure? onAuthFailure,
  required Iterable<String> objectIds,
}) async {
  final unique = uniqueObjectIds(objectIds);
  if (unique.isEmpty) {
    return {};
  }
  final merged = <String, String>{};
  try {
    for (var offset = 0; offset < unique.length; offset += kBookmarksByObjectsMax) {
      final chunk = unique.sublist(
        offset,
        offset + kBookmarksByObjectsMax > unique.length
            ? unique.length
            : offset + kBookmarksByObjectsMax,
      );
      merged.addAll(await apiClient.bookmarksByObjects(chunk));
    }
    return merged;
  } on AuthenticationException {
    onAuthFailure?.call();
    return {};
  } on ApiException {
    return {};
  }
}
