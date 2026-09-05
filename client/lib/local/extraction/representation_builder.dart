import 'dart:convert';
import 'dart:math' as math;

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
  if (utf8ByteLength(text) <= kMaxExtractedTextBytes) {
    return (text, false);
  }
  return (distributedTextSample(text, kMaxExtractedTextBytes), true);
}

String distributedTextSample(String text, int maxBytes) {
  if (maxBytes <= 0 || text.isEmpty) {
    return '';
  }
  if (utf8ByteLength(text) <= maxBytes) {
    return text;
  }
  const maxSlots = 64;
  for (var targetSlots = maxSlots; targetSlots >= 3; targetSlots--) {
    final quota = maxBytes ~/ targetSlots;
    if (quota <= 0) {
      continue;
    }
    final positions = <int>{0, text.length ~/ 2, text.length - 1};
    final remainingSlots = targetSlots - positions.length;
    for (var slot = 0; slot < remainingSlots; slot++) {
      positions.add(
        ((slot + 1) * (text.length - 1) / (remainingSlots + 1)).round(),
      );
    }
    final sortedPositions = positions.toList()..sort();
    final buffer = StringBuffer();
    var usedBytes = 0;
    var fits = true;
    for (final position in sortedPositions) {
      final slice = sliceAroundPosition(text, position, quota);
      final sliceBytes = utf8ByteLength(slice);
      if (usedBytes + sliceBytes > maxBytes) {
        fits = false;
        break;
      }
      buffer.write(slice);
      usedBytes += sliceBytes;
    }
    if (fits && usedBytes > 0) {
      return buffer.toString();
    }
  }
  return truncateToUtf8Bytes(text, maxBytes);
}

String sliceAroundPosition(String text, int position, int maxBytes) {
  if (maxBytes <= 0 || text.isEmpty) {
    return '';
  }
  final pos = position.clamp(0, math.max(0, text.length - 1)).toInt();
  final half = math.max(1, maxBytes ~/ 2);
  final start = math.max(0, pos - half).toInt();
  final end = math.min(text.length, pos + half).toInt();
  return truncateToUtf8Bytes(text.substring(start, end), maxBytes);
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
  return _buildPackedTextRepresentations(
    text: text,
    extraMeta: metadata ?? <String, dynamic>{},
    maxParts: kMaxExtractorParts,
    maxTotalBytes: kMaxExtractorTotalBytes,
  );
}

List<Map<String, dynamic>> buildBoundedTextRepresentations(
  String text,
  int maxParts, {
  Map<String, dynamic>? metadata,
}) {
  if (maxParts <= 0 || text.trim().isEmpty) {
    return [];
  }
  return _buildPackedTextRepresentations(
    text: text,
    extraMeta: metadata ?? <String, dynamic>{},
    maxParts: maxParts < kMaxExtractorParts ? maxParts : kMaxExtractorParts,
    maxTotalBytes: kMaxExtractorTotalBytes,
  );
}

List<Map<String, dynamic>> _buildPackedTextRepresentations({
  required String text,
  required Map<String, dynamic> extraMeta,
  required int maxParts,
  required int maxTotalBytes,
}) {
  final capped = capText(text);
  final cappedText = capped.$1;
  final textCapTruncated = capped.$2;
  if (cappedText.trim().length <= kSmallTextMaxChars &&
      utf8ByteLength(cappedText) <= kMaxExtractorPartBytes) {
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

  final parts = packTextIntoRepresentationParts(cappedText);
  final selectedIndices = selectRepresentationPartIndices(
    parts,
    maxParts: maxParts,
    maxTotalBytes: maxTotalBytes,
  );
  final samplingTruncated = selectedIndices.length < parts.length;
  final truncated = isTextTruncated(
    textCapTruncated: textCapTruncated,
    totalChunks: parts.length,
    selectedChunks: selectedIndices.length,
    inputReps: parts.length,
    outputReps: selectedIndices.length,
  );

  final reps = <Map<String, dynamic>>[];
  for (var slot = 0; slot < selectedIndices.length; slot++) {
    final index = selectedIndices[slot];
    reps.add({
      'kind': 'chunk',
      'text': parts[index],
      'part_index': slot,
      'metadata': {
        ...extraMeta,
        ...truncationMetadata(truncated || samplingTruncated),
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

List<String> packTextIntoRepresentationParts(String text) {
  if (text.isEmpty) {
    return [];
  }
  final parts = <String>[];
  var start = 0;
  while (start < text.length) {
    var end = maxEndForUtf8Bytes(text, start, kMaxExtractorPartBytes);
    if (end >= text.length) {
      parts.add(text.substring(start));
      break;
    }
    end = preferSplitBoundary(text, start, end);
    if (end <= start) {
      end = maxEndForUtf8Bytes(text, start, kMaxExtractorPartBytes);
      if (end <= start) {
        end = (start + 1).clamp(0, text.length);
      }
    }
    parts.add(text.substring(start, end));
    start = end;
  }
  return parts;
}

int maxEndForUtf8Bytes(String text, int start, int maxBytes) {
  if (start >= text.length || maxBytes <= 0) {
    return start;
  }
  var low = start + 1;
  var high = text.length;
  while (low < high) {
    final mid = (low + high + 1) ~/ 2;
    if (utf8ByteLength(text.substring(start, mid)) <= maxBytes) {
      low = mid;
    } else {
      high = mid - 1;
    }
  }
  return low;
}

int preferSplitBoundary(String text, int start, int candidateEnd) {
  final slice = text.substring(start, candidateEnd);
  final lastNewline = slice.lastIndexOf('\n');
  if (lastNewline > 0) {
    final newlineEnd = start + lastNewline + 1;
    if (utf8ByteLength(text.substring(start, newlineEnd)) <= kMaxExtractorPartBytes) {
      return newlineEnd;
    }
  }

  final lineStart = text.lastIndexOf('\n', candidateEnd - 1) + 1;
  final nextNewline = text.indexOf('\n', candidateEnd);
  final lineEnd = nextNewline == -1 ? text.length : nextNewline;
  if (lineStart < candidateEnd && candidateEnd < lineEnd) {
    final line = text.substring(lineStart, lineEnd);
    if (line.startsWith('[slide ') || line.startsWith('[page ')) {
      if (lineStart > start) {
        return lineStart;
      }
    }
  }
  return candidateEnd;
}

List<int> selectRepresentationPartIndices(
  List<String> parts, {
  required int maxParts,
  required int maxTotalBytes,
}) {
  if (parts.isEmpty || maxParts <= 0 || maxTotalBytes <= 0) {
    return [];
  }
  final totalBytes = parts.fold<int>(0, (sum, part) => sum + utf8ByteLength(part));
  if (parts.length <= maxParts && totalBytes <= maxTotalBytes) {
    return List.generate(parts.length, (index) => index);
  }

  final upperBound = parts.length < maxParts ? parts.length : maxParts;
  var best = <int>[];
  var low = 1;
  var high = upperBound;
  while (low <= high) {
    final candidate = (low + high) ~/ 2;
    final indices = selectBoundedIndices(parts.length, candidate);
    final bytes = _indicesByteTotal(parts, indices);
    if (bytes <= maxTotalBytes) {
      best = indices;
      low = candidate + 1;
    } else {
      high = candidate - 1;
    }
  }
  return best;
}

int _indicesByteTotal(List<String> parts, List<int> indices) {
  var total = 0;
  for (final index in indices) {
    total += utf8ByteLength(parts[index]);
  }
  return total;
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
  if (maxChunks == 2) {
    return [0, total - 1];
  }

  final anchors = <int>{0, total - 1, total ~/ 2};
  final alternateMiddle = (total - 1) ~/ 2;
  if (alternateMiddle != total ~/ 2) {
    anchors.add(alternateMiddle);
  }
  final indices = <int>[];
  final seen = <int>{};
  for (final anchor in anchors) {
    if (!seen.contains(anchor)) {
      seen.add(anchor);
      indices.add(anchor);
    }
  }
  final remaining = maxChunks - indices.length;
  for (var slot = 0; slot < remaining; slot++) {
    final index = ((slot + 1) * (total - 1) / (remaining + 1)).round();
    if (!seen.contains(index)) {
      seen.add(index);
      indices.add(index);
    }
  }
  indices.sort();
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
