import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:csv/csv.dart';

import '../client_content_revision.dart';
import 'dataset_sampling.dart';
import 'extraction_constants.dart';
import 'representation_builder.dart';

List<Map<String, dynamic>> extractCsvFile(File file) {
  final size = file.lengthSync();
  if (size <= kMaxExtractorTotalBytes) {
    return _extractSmallCsv(file);
  }
  return _extractLargeCsv(file);
}

List<Map<String, dynamic>> _extractSmallCsv(File file) {
  final text = utf8.decode(file.readAsBytesSync(), allowMalformed: true);
  final rows = const CsvToListConverter(shouldParseNumbers: false).convert(
    text,
    eol: '\n',
  );
  if (rows.isEmpty) {
    return boundedRepresentations([
      {'kind': 'schema', 'text': 'columns: (empty)'},
    ]);
  }
  final fieldnames = rows.first
      .map((cell) => cell?.toString() ?? '')
      .take(kMaxCsvColumns)
      .toList();
  final dataRows = <Map<String, String>>[];
  for (var i = 1; i < rows.length; i++) {
    final parsed = rows[i];
    dataRows.add({
      for (var col = 0; col < fieldnames.length; col++)
        fieldnames[col]:
            col < parsed.length ? parsed[col]?.toString() ?? '' : '',
    });
  }
  return _buildCsvRepresentations(fieldnames, dataRows);
}

List<Map<String, dynamic>> _extractLargeCsv(File file) {
  final fieldnames = _readCsvHeader(file);
  if (fieldnames.isEmpty) {
    return boundedRepresentations([
      {'kind': 'schema', 'text': 'columns: (empty)'},
    ]);
  }

  final stats = _streamCsvStats(file, fieldnames);
  final statsMeta = stats.$1;
  final statsLines = stats.$2;
  final columnTypes = stats.$3;
  final totalRows = statsMeta['row_count'] as int? ?? _countCsvRows(file);

  final estimateRows = _readCsvIndexedRows(file, fieldnames, [0]);
  final estimateRow = estimateRows.isNotEmpty
      ? estimateRows.first.values
      : {for (final name in fieldnames) name: ''};

  final structuralBytes = estimateStructuralBytes(
    fieldnames,
    columnTypes,
    statsLines,
  );
  final compactIndices = compactPreviewIndices(totalRows);
  final compactEstimate = formatSampleText([estimateRow], fieldnames);
  final planned = planSearchableIndices(
    totalRows: totalRows,
    fieldnames: fieldnames,
    estimateRow: estimateRow,
    structuralBytes: structuralBytes,
    compactSampleBytes: utf8ByteLength(compactEstimate),
  );
  final allIndices = {...compactIndices, ...planned.$1.indices}.toList()..sort();
  final indexedRows = _readCsvIndexedRows(file, fieldnames, allIndices);
  return buildIndexedDatasetRepresentations(
    fieldnames: fieldnames,
    columnTypes: columnTypes,
    statsMeta: statsMeta,
    statsLines: statsLines,
    totalRows: totalRows,
    indexedRows: indexedRows,
    compactIndices: compactIndices,
    searchableIndices: planned.$1.indices,
  );
}

List<Map<String, dynamic>> _buildCsvRepresentations(
  List<String> fieldnames,
  List<Map<String, String>> dataRows,
) {
  final columnTypes = {for (final name in fieldnames) name: 'string'};
  final statsMeta = <String, dynamic>{
    'row_count': dataRows.length,
    'rows_sampled': dataRows.length,
    'column_count': fieldnames.length,
    'stats_truncated': false,
    'columns': <String, dynamic>{},
  };
  final statsLines = <String>[
    'rows: ${dataRows.length}',
    'columns: ${fieldnames.length}',
  ];
  final indexedRows = [
    for (var i = 0; i < dataRows.length; i++)
      IndexedRow(index: i, values: dataRows[i]),
  ];
  final compactIndices = compactPreviewIndices(dataRows.length);
  final estimateRow = dataRows.isNotEmpty
      ? dataRows.first
      : {for (final name in fieldnames) name: ''};
  final structuralBytes = estimateStructuralBytes(
    fieldnames,
    columnTypes,
    statsLines,
  );
  final planned = planSearchableIndices(
    totalRows: dataRows.length,
    fieldnames: fieldnames,
    estimateRow: estimateRow,
    structuralBytes: structuralBytes,
    compactSampleBytes: utf8ByteLength(
      formatSampleText([estimateRow], fieldnames),
    ),
  );
  return buildIndexedDatasetRepresentations(
    fieldnames: fieldnames,
    columnTypes: columnTypes,
    statsMeta: statsMeta,
    statsLines: statsLines,
    totalRows: dataRows.length,
    indexedRows: indexedRows,
    compactIndices: compactIndices,
    searchableIndices: planned.$1.indices,
  );
}

List<String> _readCsvHeader(File file) {
  final firstLine = _iterateLines(file).first;
  if (firstLine.trim().isEmpty) {
    return [];
  }
  return const CsvToListConverter(shouldParseNumbers: false)
      .convert('$firstLine\n')
      .first
      .map((cell) => cell?.toString() ?? '')
      .take(kMaxCsvColumns)
      .toList();
}

int _countCsvRows(File file) {
  var count = 0;
  var lineNumber = 0;
  for (final line in _iterateLines(file)) {
    if (lineNumber == 0) {
      lineNumber += 1;
      continue;
    }
    if (line.trim().isNotEmpty) {
      count += 1;
    }
    lineNumber += 1;
  }
  return count;
}

(
  Map<String, dynamic>,
  List<String>,
  Map<String, String>,
) _streamCsvStats(File file, List<String> fieldnames) {
  final columnTypes = {for (final name in fieldnames) name: 'string'};
  final numericValues = {for (final name in fieldnames) name: <double>[]};
  var rowsSeen = 0;
  var truncated = false;

  final raf = file.openSync();
  try {
    var sawHeader = false;
    final buffer = StringBuffer();
    while (true) {
      final chunk = raf.readSync(8192);
      if (chunk.isEmpty && buffer.isEmpty) {
        break;
      }
      if (chunk.isNotEmpty) {
        buffer.write(utf8.decode(chunk, allowMalformed: true));
      }
      final text = buffer.toString();
      final lines = text.split('\n');
      buffer
        ..clear()
        ..write(chunk.isEmpty ? '' : lines.last);
      final completeLines =
          chunk.isEmpty ? lines : lines.sublist(0, max(0, lines.length - 1));
      for (final line in completeLines) {
        if (!sawHeader) {
          sawHeader = true;
          continue;
        }
        if (line.trim().isEmpty) {
          continue;
        }
        rowsSeen += 1;
        if (rowsSeen > kMaxCsvStatsRows) {
          truncated = true;
          break;
        }
        final parsed = const CsvToListConverter(shouldParseNumbers: false)
            .convert('$line\n')
            .first;
        for (var i = 0; i < fieldnames.length && i < parsed.length; i++) {
          final value = parsed[i]?.toString() ?? '';
          if (value.isEmpty) {
            continue;
          }
          final name = fieldnames[i];
          if (_looksInt(value)) {
            columnTypes[name] = columnTypes[name] == 'string' ? 'integer' : columnTypes[name]!;
          } else if (_looksFloat(value) && columnTypes[name] != 'integer') {
            columnTypes[name] = 'float';
          }
          final number = double.tryParse(value);
          if (number != null) {
            numericValues[name]!.add(number);
          }
        }
      }
      if (truncated || (chunk.isEmpty && buffer.isEmpty)) {
        break;
      }
    }
  } finally {
    raf.closeSync();
  }

  final statsMeta = <String, dynamic>{
    'row_count': truncated ? null : rowsSeen,
    'rows_sampled': min(rowsSeen, kMaxCsvStatsRows),
    'column_count': fieldnames.length,
    'stats_truncated': truncated,
    'columns': <String, dynamic>{},
  };
  final lines = <String>[
    'rows: ${truncated ? 'unknown (sampled)' : rowsSeen}',
    'columns: ${fieldnames.length}',
  ];
  if (truncated) {
    lines.add('rows_sampled: $kMaxCsvStatsRows');
  }
  for (final name in fieldnames) {
    final numbers = numericValues[name]!;
    if (numbers.isEmpty) {
      continue;
    }
    final minValue = numbers.reduce((a, b) => a < b ? a : b);
    final maxValue = numbers.reduce((a, b) => a > b ? a : b);
    final mean = numbers.reduce((a, b) => a + b) / numbers.length;
    statsMeta['columns'][name] = {
      'min': minValue,
      'max': maxValue,
      'mean': mean,
      'sampled': truncated,
    };
    lines.add('$name: min=$minValue, max=$maxValue, mean=$mean');
  }
  return (statsMeta, lines, columnTypes);
}

List<IndexedRow> _readCsvIndexedRows(
  File file,
  List<String> fieldnames,
  List<int> indices,
) {
  if (indices.isEmpty) {
    return [];
  }
  final wanted = indices.toSet();
  final rows = <int, Map<String, String>>{};
  var lineNumber = 0;
  for (final line in _iterateLines(file)) {
    if (lineNumber == 0) {
      lineNumber += 1;
      continue;
    }
    if (line.trim().isEmpty) {
      lineNumber += 1;
      continue;
    }
    final rowIndex = lineNumber - 1;
    if (wanted.contains(rowIndex)) {
      final parsed = const CsvToListConverter(shouldParseNumbers: false)
          .convert('$line\n')
          .first;
      rows[rowIndex] = {
        for (var i = 0; i < fieldnames.length; i++)
          fieldnames[i]: i < parsed.length ? parsed[i]?.toString() ?? '' : '',
      };
      if (rows.length == wanted.length) {
        break;
      }
    }
    lineNumber += 1;
  }
  return [
    for (final index in indices)
      if (rows.containsKey(index))
        IndexedRow(index: index, values: rows[index]!),
  ];
}

Iterable<String> _iterateLines(File file) sync* {
  final raf = file.openSync();
  final buffer = StringBuffer();
  try {
    while (true) {
      final chunk = raf.readSync(8192);
      if (chunk.isEmpty) {
        if (buffer.isNotEmpty) {
          yield buffer.toString();
        }
        break;
      }
      buffer.write(utf8.decode(chunk, allowMalformed: true));
      var text = buffer.toString();
      var newlineIndex = text.indexOf('\n');
      while (newlineIndex >= 0) {
        yield text.substring(0, newlineIndex);
        text = text.substring(newlineIndex + 1);
        newlineIndex = text.indexOf('\n');
      }
      buffer
        ..clear()
        ..write(text);
    }
  } finally {
    raf.closeSync();
  }
}

bool _looksInt(String value) => int.tryParse(value) != null;

bool _looksFloat(String value) => double.tryParse(value) != null;
