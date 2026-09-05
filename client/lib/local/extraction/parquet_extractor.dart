import 'dart:io';

import 'dart:convert';

import 'dataset_sampling.dart';
import 'duckdb_session.dart';
import 'representation_builder.dart';

Future<List<Map<String, dynamic>>> extractParquetFile(File file) async {
  return withDuckDb((session) async {
    final pathLiteral = parquetPathLiteral(file.path);
    final schemaRows = await session.queryRows(
      "DESCRIBE SELECT * FROM read_parquet($pathLiteral)",
    );
    final fieldnames = schemaRows.map((row) => row[0].toString()).toList();
    final columnTypes = {
      for (final row in schemaRows) row[0].toString(): row[1].toString(),
    };
    final countRows = await session.queryRows(
      'SELECT COUNT(*)::BIGINT FROM read_parquet($pathLiteral)',
    );
    final rowCount = (countRows.first.first as num).toInt();

    final stats = await _boundedParquetStats(
      session,
      pathLiteral,
      fieldnames,
      columnTypes,
      rowCount,
    );
    final statsMeta = stats.$1;
    final statsLines = stats.$2;

    final sampleRows = await _readParquetSampleRows(session, pathLiteral, 1);
    final estimateRow = sampleRows.isNotEmpty
        ? sampleRows.first
        : {for (final name in fieldnames) name: ''};

    final structuralBytes = estimateStructuralBytes(
      fieldnames,
      columnTypes,
      statsLines,
    );
    final compactIndices = compactPreviewIndices(rowCount);
    final compactEstimate = formatSampleText(
      [
        {
          for (final name in fieldnames)
            name: estimateRow[name]?.toString() ?? '',
        },
      ],
      fieldnames,
    );
    final planned = planSearchableIndices(
      totalRows: rowCount,
      fieldnames: fieldnames,
      estimateRow: {
        for (final name in fieldnames)
          name: estimateRow[name]?.toString() ?? '',
      },
      structuralBytes: structuralBytes,
      compactSampleBytes: utf8.encode(compactEstimate).length,
    );
    final allIndices = {...compactIndices, ...planned.$1.indices}.toList()
      ..sort();
    final indexedRows = await _readParquetIndexedRows(
      session,
      pathLiteral,
      fieldnames,
      allIndices,
    );
    return buildIndexedDatasetRepresentations(
      fieldnames: fieldnames,
      columnTypes: columnTypes,
      statsMeta: statsMeta,
      statsLines: statsLines,
      totalRows: rowCount,
      indexedRows: indexedRows,
      compactIndices: compactIndices,
      searchableIndices: planned.$1.indices,
    );
  });
}

Future<(Map<String, dynamic>, List<String>)> _boundedParquetStats(
  DuckDbSession session,
  String pathLiteral,
  List<String> fieldnames,
  Map<String, String> columnTypes,
  int rowCount,
) async {
  const maxRows = 5000;
  final truncated = rowCount > maxRows;
  final numericStats = <String, Map<String, dynamic>>{};
  final sampleLimit = rowCount < maxRows ? rowCount : maxRows;
  if (sampleLimit > 0) {
    final rows = await session.queryRows(
      'SELECT * FROM read_parquet($pathLiteral) LIMIT $sampleLimit',
    );
    for (final row in rows) {
      for (var i = 0; i < fieldnames.length; i++) {
        final name = fieldnames[i];
        final value = row[i];
        if (value == null) {
          continue;
        }
        final type = columnTypes[name] ?? '';
        if (!type.contains('INT') &&
            !type.contains('DOUBLE') &&
            !type.contains('FLOAT') &&
            !type.contains('DECIMAL')) {
          continue;
        }
        final number = (value as num).toDouble();
        final current = numericStats.putIfAbsent(
          name,
          () => {
            'min': number,
            'max': number,
            'sum': 0.0,
            'count': 0,
          },
        );
        current['min'] = (current['min'] as double) < number
            ? current['min']
            : number;
        current['max'] = (current['max'] as double) > number
            ? current['max']
            : number;
        current['sum'] = (current['sum'] as double) + number;
        current['count'] = (current['count'] as int) + 1;
      }
    }
  }

  final statsMeta = <String, dynamic>{
    'row_count': rowCount,
    'rows_sampled': sampleLimit,
    'column_count': fieldnames.length,
    'stats_truncated': truncated,
    'columns': <String, dynamic>{},
  };
  final lines = <String>[
    'rows: $rowCount',
    'columns: ${fieldnames.length}',
  ];
  if (truncated) {
    lines.add('rows_sampled: $maxRows');
  }
  for (final entry in numericStats.entries) {
    final count = entry.value['count'] as int;
    final mean = (entry.value['sum'] as double) / count;
    final colStats = {
      'min': entry.value['min'],
      'max': entry.value['max'],
      'mean': mean,
      'sampled': truncated,
    };
    statsMeta['columns'][entry.key] = colStats;
    lines.add(
      '${entry.key}: min=${colStats['min']}, max=${colStats['max']}, mean=$mean',
    );
  }
  return (statsMeta, lines);
}

Future<List<Map<String, dynamic>>> _readParquetSampleRows(
  DuckDbSession session,
  String pathLiteral,
  int limit,
) async {
  final rows = await session.queryRows(
    'SELECT * FROM read_parquet($pathLiteral) LIMIT $limit',
  );
  if (rows.isEmpty) {
    return [];
  }
  final fieldnames = await _parquetFieldnames(session, pathLiteral);
  return [
    for (final row in rows)
      {
        for (var i = 0; i < fieldnames.length; i++)
          fieldnames[i]: row[i]?.toString() ?? '',
      },
  ];
}

Future<List<String>> _parquetFieldnames(
  DuckDbSession session,
  String pathLiteral,
) async {
  final schemaRows = await session.queryRows(
    "DESCRIBE SELECT * FROM read_parquet($pathLiteral)",
  );
  return schemaRows.map((row) => row[0].toString()).toList();
}

Future<List<IndexedRow>> _readParquetIndexedRows(
  DuckDbSession session,
  String pathLiteral,
  List<String> fieldnames,
  List<int> indices,
) async {
  if (indices.isEmpty) {
    return [];
  }
  final wanted = indices.toSet().toList()..sort();
  final inList = wanted.join(', ');
  final rows = await session.queryRows(
    'WITH numbered AS ('
    'SELECT row_number() OVER () - 1 AS idx, * '
    'FROM read_parquet($pathLiteral)'
    ') SELECT * FROM numbered WHERE idx IN ($inList) ORDER BY idx',
  );
  return [
    for (final row in rows)
      IndexedRow(
        index: (row.first as num).toInt(),
        values: {
          for (var i = 0; i < fieldnames.length; i++)
            fieldnames[i]: row[i + 1]?.toString() ?? '',
        },
      ),
  ];
}
