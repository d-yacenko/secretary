import 'dart:convert';
import 'dart:io';

import 'package:archive/archive.dart';
import 'package:xml/xml.dart';

import '../client_content_revision.dart';
import 'archive_xml_utils.dart';
import 'dataset_sampling.dart';
import 'extraction_constants.dart';
import 'representation_builder.dart';

const _officeNs = 'urn:oasis:names:tc:opendocument:xmlns:office:1.0';
const _textNs = 'urn:oasis:names:tc:opendocument:xmlns:text:1.0';
const _tableNs = 'urn:oasis:names:tc:opendocument:xmlns:table:1.0';
const _drawNs = 'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0';

Future<List<Map<String, dynamic>>> extractOdtFile(File file) async {
  final root = await _readOdfContentXml(file);
  final body = _firstByLocal(root, 'body', 'office');
  if (body == null) {
    throw const FormatException('missing office:body');
  }
  final officeText = _firstChildByLocal(body, 'text', 'office');
  if (officeText == null) {
    throw const FormatException('missing office:text');
  }

  final lines = <String>[];
  for (final child in officeText.childElements) {
    if (_isTag(child, 'h', 'text') || _isTag(child, 'p', 'text')) {
      final text = elementText(child);
      if (text.isNotEmpty) {
        lines.add(text);
      }
    } else if (_isTag(child, 'list', 'text')) {
      lines.addAll(_odtListItems(child));
    } else if (_isTag(child, 'table', 'table')) {
      lines.addAll(_odtTableRows(child));
    }
  }

  final text = lines.join('\n');
  if (text.trim().isEmpty) {
    throw const FormatException('no_extractable_text');
  }
  return buildTextRepresentations(text);
}

Future<List<Map<String, dynamic>>> extractOdpFile(File file) async {
  final root = await _readOdfContentXml(file);
  final body = _firstByLocal(root, 'body', 'office');
  if (body == null) {
    throw const FormatException('missing office:body');
  }
  final presentation = _firstChildByLocal(body, 'presentation', 'office');
  if (presentation == null) {
    throw const FormatException('missing office:presentation');
  }

  final pages = presentation.childElements
      .where((child) => _isTag(child, 'page', 'draw'))
      .toList();
  var truncated = pages.length > kMaxOdpSlides;
  final selected = pages.take(kMaxOdpSlides).toList();
  final lines = <String>[];
  for (var index = 0; index < selected.length; index++) {
    lines.add('[slide ${index + 1}]');
    lines.addAll(_odpPageText(selected[index]));
  }
  final text = lines.join('\n');
  if (text.trim().isEmpty) {
    throw const FormatException('no_extractable_text');
  }
  return buildTextRepresentations(
    text,
    metadata: {'slide_count': selected.length, 'truncated': truncated},
  );
}

Future<List<Map<String, dynamic>>> extractOdsFile(File file) async {
  final root = await _readOdfContentXml(file);
  final body = _firstByLocal(root, 'body', 'office');
  if (body == null) {
    throw const FormatException('missing office:body');
  }
  final spreadsheet = _firstChildByLocal(body, 'spreadsheet', 'office');
  if (spreadsheet == null) {
    throw const FormatException('missing office:spreadsheet');
  }

  final tables = spreadsheet.childElements
      .where((child) => _isTag(child, 'table', 'table'))
      .toList();
  var truncated = tables.length > kMaxOdfSheets;
  final selectedTables = tables.take(kMaxOdfSheets).toList();

  final schemaLines = <String>['schema'];
  final sampleLines = <String>['sample'];
  final statsLines = <String>['statistics'];
  final searchableLines = <String>[];
  final allRows = <IndexedRow>[];
  var totalRows = 0;

  for (final table in selectedTables) {
    final sheetName = table.getAttribute('name', namespace: _tableNs) ?? 'Sheet';
    final parsed = _odsTableRows(table);
    truncated = truncated || parsed.$2;
    final rows = parsed.$1;
    if (rows.isEmpty) {
      schemaLines.add('$sheetName: (empty)');
      statsLines.add('$sheetName: rows=0, columns=0');
      continue;
    }
    final header = rows.first;
    final fieldnames = header.values.keys.toList();
    final dataRows = rows.sublist(1);
    totalRows += dataRows.length;
    schemaLines.add(
      '$sheetName: ${fieldnames.map((name) => '$name=string').join(', ')}',
    );
    sampleLines.add('[$sheetName]');
    sampleLines.add(_formatOdsRow(0, header.values));
    for (var i = 0; i < dataRows.length && i < 5; i++) {
      sampleLines.add(_formatOdsRow(dataRows[i].index, dataRows[i].values));
    }
    statsLines.add(
      '$sheetName: rows=${dataRows.length}, columns=${fieldnames.length}',
    );
    for (final row in dataRows) {
      searchableLines.add(
        '[sheet=$sheetName row=${row.index + 1}]\n${_formatOdsValues(row.values, fieldnames)}',
      );
      allRows.add(row);
    }
  }

  if (allRows.isEmpty) {
    throw const FormatException('no_extractable_text');
  }

  final fieldnames = allRows.first.values.keys.toList();
  final columnTypes = {for (final name in fieldnames) name: 'string'};
  final statsMeta = <String, dynamic>{
    'row_count': totalRows,
    'rows_sampled': totalRows,
    'column_count': fieldnames.length,
    'stats_truncated': truncated,
    'columns': <String, dynamic>{},
  };

  if (totalRows <= kCompactSampleMaxRows) {
    final schemaCapped = capStructuralText(schemaLines.join('\n'));
    final sampleCapped = capStructuralText(sampleLines.join('\n'));
    final statsCapped = capStructuralText(statsLines.join('\n'));
    final searchableReps = buildBoundedTextRepresentations(
      searchableLines.join('\n'),
      kMaxExtractorParts - kDatasetStructuralParts,
    );
    return boundedRepresentations([
      {'kind': 'schema', 'text': schemaCapped.$1, 'metadata': statsMeta},
      {'kind': 'sample', 'text': sampleCapped.$1},
      {'kind': 'statistics', 'text': statsCapped.$1, 'metadata': statsMeta},
      ...searchableReps,
    ]);
  }

  final estimateRow = allRows.first.values;
  final structuralBytes = estimateStructuralBytes(
    fieldnames,
    columnTypes,
    statsLines,
  );
  final compactIndices = compactPreviewIndices(totalRows);
  final planned = planSearchableIndices(
    totalRows: totalRows,
    fieldnames: fieldnames,
    estimateRow: estimateRow,
    structuralBytes: structuralBytes,
    compactSampleBytes: utf8ByteLength(
      formatSampleText([estimateRow], fieldnames),
    ),
  );
  final indexedRows = [
    for (var i = 0; i < allRows.length; i++)
      IndexedRow(index: i, values: allRows[i].values),
  ];
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

Future<XmlElement> _readOdfContentXml(File file) async {
  final archive = await readZipArchive(file);
  if (!archive.files.any((entry) => entry.name == 'content.xml')) {
    throw const FormatException('missing content.xml');
  }
  return parseSafeXml(readArchiveEntry(archive, 'content.xml')).rootElement;
}

(List<IndexedRow>, bool) _odsTableRows(XmlElement table) {
  final rows = <IndexedRow>[];
  var truncated = false;
  var rowIndex = 0;
  for (final rowElem in _childrenByLocal(table, 'table-row', 'table')) {
    if (rows.length >= kMaxOdfRowsPerSheet) {
      truncated = true;
      break;
    }
    final values = <String, String>{};
    var colIndex = 0;
    for (final cell in _childrenByLocal(rowElem, 'table-cell', 'table')) {
      final cellRepeat = _boundedRepeat(
        cell.getAttribute('number-columns-repeated', namespace: _tableNs),
      );
      final cellText = elementText(cell);
      for (var i = 0; i < cellRepeat.$1; i++) {
        if (colIndex >= kMaxOdfColumns) {
          truncated = true;
          break;
        }
        values['col_$colIndex'] = cellText;
        colIndex += 1;
      }
      truncated = truncated || cellRepeat.$2;
      if (truncated) {
        break;
      }
    }
    final rowRepeat = _boundedRepeat(
      rowElem.getAttribute('number-rows-repeated', namespace: _tableNs),
    );
    truncated = truncated || rowRepeat.$2;
    for (var i = 0; i < rowRepeat.$1; i++) {
      if (values.values.any((value) => value.isNotEmpty)) {
        rows.add(IndexedRow(index: rowIndex, values: Map.from(values)));
      }
      rowIndex += 1;
      if (rows.length >= kMaxOdfRowsPerSheet) {
        truncated = true;
        break;
      }
    }
  }
  return (rows, truncated);
}

(int, bool) _boundedRepeat(String? raw, {int defaultValue = 1}) {
  if (raw == null || raw.isEmpty) {
    return (defaultValue, false);
  }
  final value = int.tryParse(raw) ?? defaultValue;
  if (value > kMaxOdfRepeatExpansion) {
    return (kMaxOdfRepeatExpansion, true);
  }
  if (value < 1) {
    return (1, false);
  }
  return (value, false);
}

List<String> _odtListItems(XmlElement listElem) {
  final items = <String>[];
  for (final item in listElem.descendants.whereType<XmlElement>()) {
    if (_isTag(item, 'list-item', 'text')) {
      final text = elementText(item);
      if (text.isNotEmpty) {
        items.add('- $text');
      }
    }
  }
  return items;
}

List<String> _odtTableRows(XmlElement table) {
  final lines = <String>[];
  for (final rowElem in _childrenByLocal(table, 'table-row', 'table')) {
    final rowCells = <String>[];
    for (final cell in _childrenByLocal(rowElem, 'table-cell', 'table')) {
      final repeat = _boundedRepeat(
        cell.getAttribute('number-columns-repeated', namespace: _tableNs),
      );
      final cellText = elementText(cell);
      for (var i = 0; i < repeat.$1; i++) {
        if (rowCells.length >= kMaxOdfColumns) {
          break;
        }
        rowCells.add(cellText);
      }
    }
    if (rowCells.any((cell) => cell.isNotEmpty)) {
      lines.add('| ${rowCells.join(' | ')} |');
    }
  }
  return lines;
}

List<String> _odpPageText(XmlElement page) {
  final lines = <String>[];
  for (final element in page.descendants.whereType<XmlElement>()) {
    if (_isTag(element, 'p', 'text')) {
      final text = elementText(element);
      if (text.isNotEmpty) {
        lines.add(text);
      }
    } else if (_isTag(element, 'list', 'text')) {
      lines.addAll(_odtListItems(element));
    } else if (_isTag(element, 'table', 'table')) {
      lines.addAll(_odtTableRows(element));
    }
  }
  return lines;
}

String _formatOdsRow(int index, Map<String, String> values) {
  return 'row=${index + 1} ${values.entries.map((e) => '${e.key}=${e.value}').join(' | ')}';
}

String _formatOdsValues(Map<String, String> values, List<String> fieldnames) {
  return fieldnames.map((name) => values[name] ?? '').join(',');
}

bool _isTag(XmlElement element, String local, String nsKey) {
  final namespace = switch (nsKey) {
    'office' => _officeNs,
    'text' => _textNs,
    'table' => _tableNs,
    'draw' => _drawNs,
    _ => '',
  };
  return element.name.local == local && element.name.namespaceUri == namespace;
}

XmlElement? _firstByLocal(XmlElement root, String local, String nsKey) {
  for (final element in root.descendants.whereType<XmlElement>()) {
    if (_isTag(element, local, nsKey)) {
      return element;
    }
  }
  return null;
}

XmlElement? _firstChildByLocal(XmlElement parent, String local, String nsKey) {
  for (final child in parent.childElements) {
    if (_isTag(child, local, nsKey)) {
      return child;
    }
  }
  return null;
}

Iterable<XmlElement> _childrenByLocal(
  XmlElement parent,
  String local,
  String nsKey,
) {
  return parent.childElements.where((child) => _isTag(child, local, nsKey));
}
