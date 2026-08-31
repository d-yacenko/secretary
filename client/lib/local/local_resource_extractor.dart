import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:path/path.dart' as p;

/// Mechanical local file extraction bounds (PHASE 26B).
const int kMaxExtractorParts = 64;
const int kMaxExtractorPartChars = 16 * 1024;
const int kMaxExtractorTotalChars = 256 * 1024;
const int kSmallTextMaxChars = 500;
const int kChunkSize = 800;
const int kChunkOverlap = 100;
const int kMaxCsvSampleRows = 20;
const int kMaxCsvColumns = 100;
const int kMaxCsvStatsRows = 5000;
const int kCheapHashMaxBytes = 256 * 1024;
const int kReadWindowBytes = 8000;

const _supportedSuffixes = {'.txt', '.md', '.csv'};

class LocalExtractionResult {
  const LocalExtractionResult({
    required this.sourcePath,
    required this.filename,
    required this.extension,
    required this.size,
    required this.modifiedAt,
    required this.contentRevision,
    required this.suggestedKind,
    required this.metadataOnly,
    required this.representations,
    this.contentHash,
    this.userMessage,
    this.extractionFailed = false,
  });

  final String sourcePath;
  final String filename;
  final String extension;
  final int size;
  final String modifiedAt;
  final String contentRevision;
  final String suggestedKind;
  final bool metadataOnly;
  final List<Map<String, dynamic>> representations;
  final String? contentHash;
  final String? userMessage;
  final bool extractionFailed;
}

class LocalResourceExtractor {
  LocalExtractionResult extractFile(File file) {
    final path = file.path;
    final stat = file.statSync();
    final filename = p.basename(path);
    final extension = p.extension(filename).toLowerCase();
    final modifiedAt = stat.modified.toUtc().toIso8601String();
    final size = stat.size;

    String? contentHash;
    if (size <= kCheapHashMaxBytes) {
      final digest = sha256.convert(file.readAsBytesSync());
      contentHash = digest.toString();
    }

    final revision = _buildRevision(path, size, modifiedAt, contentHash);

    if (!_supportedSuffixes.contains(extension)) {
      return LocalExtractionResult(
        sourcePath: path,
        filename: filename,
        extension: extension,
        size: size,
        modifiedAt: modifiedAt,
        contentRevision: revision,
        suggestedKind: 'file',
        metadataOnly: true,
        representations: [],
        contentHash: contentHash,
        userMessage: 'Формат пока индексируется только по метаданным',
      );
    }

    try {
      final reps = extension == '.csv'
          ? _extractCsv(file)
          : _extractText(file, extension);
      return LocalExtractionResult(
        sourcePath: path,
        filename: filename,
        extension: extension,
        size: size,
        modifiedAt: modifiedAt,
        contentRevision: revision,
        suggestedKind: extension == '.csv' ? 'dataset' : 'document',
        metadataOnly: false,
        representations: reps,
        contentHash: contentHash,
      );
    } catch (_) {
      return LocalExtractionResult(
        sourcePath: path,
        filename: filename,
        extension: extension,
        size: size,
        modifiedAt: modifiedAt,
        contentRevision: revision,
        suggestedKind: extension == '.csv' ? 'dataset' : 'document',
        metadataOnly: true,
        representations: [],
        contentHash: contentHash,
        userMessage: 'Не удалось прочитать файл',
        extractionFailed: true,
      );
    }
  }

  List<Map<String, dynamic>> _extractText(File file, String extension) {
    final bytes = _readBoundedBytes(file);
    final text = utf8.decode(bytes, allowMalformed: true);
    if (text.trim().length <= kSmallTextMaxChars) {
      return [
        {'kind': 'full', 'text': text},
      ];
    }
    final chunks = _chunkText(text, kChunkSize, kChunkOverlap);
    final indices = _selectBoundedIndices(chunks.length, kMaxExtractorParts);
    final reps = <Map<String, dynamic>>[];
    var total = 0;
    for (var slot = 0; slot < indices.length; slot++) {
      final index = indices[slot];
      final chunk = chunks[index];
      if (chunk.length > kMaxExtractorPartChars) {
        continue;
      }
      total += chunk.length;
      if (total > kMaxExtractorTotalChars) {
        break;
      }
      reps.add({
        'kind': 'chunk',
        'text': chunk,
        'part_index': slot,
        'metadata': {'source_chunk_index': index},
      });
    }
    return reps;
  }

  List<Map<String, dynamic>> _extractCsv(File file) {
    final text = utf8.decode(_readBoundedBytes(file), allowMalformed: true);
    final lines = text.split('\n').take(kMaxCsvStatsRows + 1).toList();

    if (lines.isEmpty) {
      return [
        {'kind': 'schema', 'text': 'columns: (empty)'},
      ];
    }

    final headerLine = lines.first;
    final columns = _parseCsvLine(headerLine).take(kMaxCsvColumns).toList();
    final schemaText = 'columns: ${columns.join(', ')}';

    final sampleRows = <List<String>>[];
    for (var i = 1; i < lines.length && sampleRows.length < kMaxCsvSampleRows; i++) {
      sampleRows.add(_parseCsvLine(lines[i]).take(kMaxCsvColumns).toList());
    }
    final sampleText = sampleRows
        .map((row) => row.join('\t'))
        .join('\n');

    final statsLines = <String>['row_count_inspected: ${lines.length - 1}'];
    for (final col in columns) {
      statsLines.add('column $col: type=text');
    }

    return [
      {'kind': 'schema', 'text': schemaText},
      {'kind': 'sample', 'text': sampleText},
      {'kind': 'statistics', 'text': statsLines.join('\n')},
    ];
  }

  List<String> _parseCsvLine(String line) {
    // Minimal CSV split for mechanical sampling; not a full CSV parser.
    if (line.trim().isEmpty) {
      return [];
    }
    return line.split(',').map((v) => v.trim()).toList();
  }

  List<int> _readBoundedBytes(File file) {
    final size = file.lengthSync();
    if (size <= kMaxExtractorTotalChars) {
      return file.readAsBytesSync();
    }
    final raf = file.openSync();
    try {
      final windows = <int>{0};
      if (size > kReadWindowBytes) {
        windows.add(max(0, (size ~/ 2) - (kReadWindowBytes ~/ 2)));
        windows.add(max(0, size - kReadWindowBytes));
      }
      final buffer = <int>[];
      for (final offset in windows) {
        raf.setPositionSync(offset);
        final toRead = min(kReadWindowBytes, size - offset);
        buffer.addAll(raf.readSync(toRead));
        if (buffer.length >= kMaxExtractorTotalChars) {
          break;
        }
      }
      return buffer.take(kMaxExtractorTotalChars).toList();
    } finally {
      raf.closeSync();
    }
  }

  List<String> _chunkText(String text, int chunkSize, int overlap) {
    if (chunkSize <= 0 || text.isEmpty) {
      return [];
    }
    final chunks = <String>[];
    var start = 0;
    while (start < text.length) {
      final end = min(start + chunkSize, text.length);
      chunks.add(text.substring(start, end));
      if (end >= text.length) {
        break;
      }
      start = end - overlap;
    }
    return chunks;
  }

  List<int> _selectBoundedIndices(int total, int maxChunks) {
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

  String _buildRevision(
    String path,
    int size,
    String modifiedAt,
    String? contentHash,
  ) {
    final parts = <String>[
      'modified_at=$modifiedAt',
      'size=$size',
      'source_path=${path.replaceAll('\\', '/')}',
    ];
    if (contentHash != null) {
      parts.add('content_hash=$contentHash');
    }
    parts.sort();
    final payload = parts.join('|');
    return sha256.convert(utf8.encode(payload)).toString();
  }
}
