import 'dart:convert';

import '../client_content_revision.dart';
import 'extraction_constants.dart';

List<Map<String, dynamic>> boundedRepresentations(
  List<Map<String, dynamic>> reps,
) {
  final bounded = <Map<String, dynamic>>[];
  var totalBytes = 0;
  for (final rep in reps) {
    if (bounded.length >= kMaxExtractorParts) {
      break;
    }
    final text = rep['text'] as String? ?? '';
    final partText = truncateToUtf8Bytes(text, kMaxExtractorPartBytes);
    final partBytes = utf8ByteLength(partText);
    if (totalBytes + partBytes > kMaxExtractorTotalBytes) {
      break;
    }
    totalBytes += partBytes;
    bounded.add({
      ...rep,
      'text': partText,
    });
  }
  return bounded;
}

(String, bool) capStructuralText(String text) {
  final bytes = utf8.encode(text);
  if (bytes.length <= kMaxExtractorPartBytes) {
    return (text, false);
  }
  return (
    truncateToUtf8Bytes(text, kMaxExtractorPartBytes),
    true,
  );
}

(String, bool) capText(String text) {
  if (text.length <= kMaxExtractedTextChars) {
    return (text, false);
  }
  return (text.substring(0, kMaxExtractedTextChars), true);
}

Map<String, dynamic> truncationMetadata(bool truncated) {
  if (!truncated) {
    return {};
  }
  return {'truncated': true};
}

bool isTextTruncated({
  required bool textCapTruncated,
  required int totalChunks,
  required int selectedChunks,
  required int inputReps,
  required int outputReps,
}) {
  return textCapTruncated ||
      (totalChunks > 0 && selectedChunks < totalChunks) ||
      (inputReps > 0 && outputReps < inputReps);
}

List<Map<String, dynamic>> buildTextRepresentations(
  String text, {
  Map<String, dynamic>? metadata,
}) {
  final extraMeta = metadata ?? <String, dynamic>{};
  final capped = capText(text);
  final cappedText = capped.$1;
  final textCapTruncated = capped.$2;
  if (cappedText.trim().length <= kSmallTextMaxChars &&
      utf8ByteLength(cappedText) <= kMaxExtractorPartBytes) {
    final reps = boundedRepresentations([
      {
        'kind': 'full',
        'text': cappedText,
        'metadata': {
          ...extraMeta,
          ...truncationMetadata(textCapTruncated),
        },
      },
    ]);
    return reps;
  }
  final chunks = chunkText(cappedText, kChunkSize, kChunkOverlap);
  final indices = selectBoundedIndices(chunks.length, kMaxExtractorParts);
  final truncated = isTextTruncated(
    textCapTruncated: textCapTruncated,
    totalChunks: chunks.length,
    selectedChunks: indices.length,
    inputReps: indices.length,
    outputReps: indices.length,
  );
  final reps = <Map<String, dynamic>>[];
  for (var slot = 0; slot < indices.length; slot++) {
    final index = indices[slot];
    reps.add({
      'kind': 'chunk',
      'text': chunks[index],
      'part_index': slot,
      'metadata': {
        ...extraMeta,
        ...truncationMetadata(truncated),
        'source_chunk_index': index,
      },
    });
  }
  final bounded = boundedRepresentations(reps);
  if (bounded.length < reps.length) {
    return [
      for (final rep in bounded)
        {
          ...rep,
          'metadata': {
            ...(rep['metadata'] as Map<String, dynamic>? ?? {}),
            ...truncationMetadata(true),
          },
        },
    ];
  }
  return bounded;
}

List<String> chunkText(String text, int chunkSize, int overlap) {
  if (chunkSize <= 0 || text.isEmpty) {
    return [];
  }
  final chunks = <String>[];
  var start = 0;
  while (start < text.length) {
    final end = start + chunkSize > text.length ? text.length : start + chunkSize;
    chunks.add(text.substring(start, end));
    if (end >= text.length) {
      break;
    }
    start = end - overlap;
  }
  return chunks;
}

List<int> selectBoundedIndices(int total, int maxChunks) {
  if (total <= 0 || maxChunks <= 0) {
    return [];
  }
  if (total <= maxChunks) {
    return List.generate(total, (i) => i);
  }
  if (maxChunks == 1) {
    return [0];
  }
  final indices = <int>[];
  final seen = <int>{};
  for (var slot = 0; slot < maxChunks; slot++) {
    final index = ((slot * (total - 1)) / (maxChunks - 1)).round();
    if (!seen.contains(index)) {
      seen.add(index);
      indices.add(index);
    }
  }
  return indices;
}

String formatSchemaText(
  List<String> fieldnames,
  Map<String, String> columnTypes,
) {
  final parts = fieldnames
      .map((name) => '$name:${columnTypes[name] ?? 'string'}')
      .join(', ');
  return 'schema\ncolumns: $parts';
}

String formatSampleText(
  List<Map<String, String>> rows,
  List<String> fieldnames,
) {
  final lines = <String>['sample', fieldnames.join(',')];
  for (final row in rows) {
    lines.add(fieldnames.map((name) => row[name] ?? '').join(','));
  }
  return lines.join('\n');
}

List<Map<String, dynamic>> buildBoundedTextRepresentations(
  String text,
  int maxParts, {
  Map<String, dynamic>? metadata,
}) {
  if (maxParts <= 0 || text.trim().isEmpty) {
    return [];
  }
  final extraMeta = metadata ?? <String, dynamic>{};
  final capped = capText(text);
  final cappedText = capped.$1;
  final textCapTruncated = capped.$2;
  if (cappedText.length <= kSmallTextMaxChars) {
    return boundedRepresentations([
      {
        'kind': 'full',
        'text': cappedText,
        'metadata': {
          ...extraMeta,
          ...truncationMetadata(textCapTruncated),
        },
      },
    ]);
  }
  final chunks = chunkText(cappedText, kChunkSize, kChunkOverlap);
  final maxChunks = maxParts < kMaxExtractorParts ? maxParts : kMaxExtractorParts;
  final indices = selectBoundedIndices(chunks.length, maxChunks);
  final truncated = isTextTruncated(
    textCapTruncated: textCapTruncated,
    totalChunks: chunks.length,
    selectedChunks: indices.length,
    inputReps: indices.length,
    outputReps: indices.length,
  );
  final reps = <Map<String, dynamic>>[];
  for (var slot = 0; slot < indices.length; slot++) {
    final index = indices[slot];
    reps.add({
      'kind': 'chunk',
      'text': chunks[index],
      'part_index': slot,
      'metadata': {
        ...extraMeta,
        ...truncationMetadata(truncated),
        'source_chunk_index': index,
      },
    });
  }
  final bounded = boundedRepresentations(reps);
  if (bounded.length < reps.length) {
    return [
      for (final rep in bounded)
        {
          ...rep,
          'metadata': {
            ...(rep['metadata'] as Map<String, dynamic>? ?? {}),
            ...truncationMetadata(true),
          },
        },
    ];
  }
  return bounded;
}
