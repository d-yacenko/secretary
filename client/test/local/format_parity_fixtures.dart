import 'dart:convert';
import 'dart:io';
import 'dart:ui';

import 'package:archive/archive.dart';
import 'package:personal_secretary/local/extraction/duckdb_session.dart';
import 'package:syncfusion_flutter_pdf/pdf.dart';

Future<void> writeMinimalPdf(File file, {String text = 'pdf distinctive phrase delta'}) async {
  final document = PdfDocument();
  final page = document.pages.add();
  page.graphics.drawString(
    text,
    PdfStandardFont(PdfFontFamily.helvetica, 12),
    bounds: const Rect.fromLTWH(20, 20, 500, 20),
  );
  final bytes = await document.save();
  document.dispose();
  await file.writeAsBytes(bytes);
}

List<int> _minimalPdfBytes(String text) {
  final escaped = text
      .replaceAll('\\', r'\\')
      .replaceAll('(', r'\(')
      .replaceAll(')', r'\)');
  final stream = 'BT /F1 12 Tf 50 700 Td ($escaped) Tj ET';
  final objs = <String>[
    '1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n',
    '2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n',
    '3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        '/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n',
    '4 0 obj<< /Length ${stream.length} >>stream\n$stream\nendstream endobj\n',
    '5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n',
  ];
  final header = utf8.encode('%PDF-1.4\n');
  final bodyParts = <List<int>>[];
  final xrefPositions = <int>[];
  var pos = header.length;
  for (final obj in objs) {
    xrefPositions.add(pos);
    final chunk = utf8.encode(obj);
    bodyParts.add(chunk);
    pos += chunk.length;
  }
  final body = bodyParts.expand((part) => part).toList();
  final xrefStart = pos;
  final xrefLines = <String>[
    'xref\n',
    '0 ${objs.length + 1}\n',
    '0000000000 65535 f \n',
    for (final offset in xrefPositions) '${offset.toString().padLeft(10, '0')} 00000 n \n',
  ];
  final xref = utf8.encode(xrefLines.join());
  final trailer = utf8.encode(
    'trailer<< /Size ${objs.length + 1} /Root 1 0 R >>\n'
    'startxref\n$xrefStart\n%%EOF\n',
  );
  return [...header, ...body, ...xref, ...trailer];
}

Future<void> writeBlankPdf(File file) async {
  await file.writeAsBytes(_blankPdfBytes());
}

List<int> _blankPdfBytes() {
  final objs = <String>[
    '1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n',
    '2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n',
    '3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>endobj\n',
  ];
  final header = utf8.encode('%PDF-1.4\n');
  final bodyParts = <List<int>>[];
  final xrefPositions = <int>[];
  var pos = header.length;
  for (final obj in objs) {
    xrefPositions.add(pos);
    final chunk = utf8.encode(obj);
    bodyParts.add(chunk);
    pos += chunk.length;
  }
  final body = bodyParts.expand((part) => part).toList();
  final xrefStart = pos;
  final xrefLines = <String>[
    'xref\n',
    '0 ${objs.length + 1}\n',
    '0000000000 65535 f \n',
    for (final offset in xrefPositions) '${offset.toString().padLeft(10, '0')} 00000 n \n',
  ];
  final xref = utf8.encode(xrefLines.join());
  final trailer = utf8.encode(
    'trailer<< /Size ${objs.length + 1} /Root 1 0 R >>\n'
    'startxref\n$xrefStart\n%%EOF\n',
  );
  return [...header, ...body, ...xref, ...trailer];
}

Future<void> writeMultiPagePdf(File file, int pages, {String marker = 'page_marker'}) async {
  final document = PdfDocument();
  for (var index = 0; index < pages; index++) {
    final page = document.pages.add();
    page.graphics.drawString(
      '$marker-$index',
      PdfStandardFont(PdfFontFamily.helvetica, 12),
      bounds: const Rect.fromLTWH(20, 20, 400, 20),
    );
  }
  final bytes = await document.save();
  document.dispose();
  await file.writeAsBytes(bytes);
}

Future<void> writeMinimalDocx(File file, {String text = 'docx paragraph beta'}) async {
  final documentXml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>$text</w:t></w:r></w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>cell1</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>cell2</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>''';
  await _writeOoxmlZip(file, {
    'word/document.xml': documentXml,
    '[Content_Types].xml': _contentTypesXml(
      '/word/document.xml',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml',
    ),
  });
}

Future<void> writeMinimalXlsx(File file) async {
  final workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>''';
  final rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>''';
  final sheet1 = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="inlineStr"><is><t>col_a</t></is></c><c r="B1" t="inlineStr"><is><t>col_b</t></is></c></row>
    <row r="2"><c r="A2" t="inlineStr"><is><t>xlsx_value</t></is></c><c r="B2" t="inlineStr"><is><t>2</t></is></c></row>
  </sheetData>
</worksheet>''';
  await _writeOoxmlZip(file, {
    '[Content_Types].xml': _genericContentTypes(),
    'xl/workbook.xml': workbook,
    'xl/_rels/workbook.xml.rels': rels,
    'xl/worksheets/sheet1.xml': sheet1,
  });
}

Future<void> writeMinimalPptx(File file, {String text = 'slide distinctive gamma'}) async {
  final slide = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>
    <p:sp><p:txBody><a:p><a:r><a:t>$text</a:t></a:r></a:p></p:txBody></p:sp>
  </p:spTree></p:cSld>
</p:sld>''';
  await _writeOoxmlZip(file, {
    '[Content_Types].xml': _genericContentTypes(),
    'ppt/slides/slide1.xml': slide,
  });
}

Future<void> writeMinimalOdt(File file, {String paragraph = 'odt distinctive alpha'}) async {
  final contentXml = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0">
  <office:body>
    <office:text>
      <text:h>ODT Heading</text:h>
      <text:p>$paragraph</text:p>
      <text:list><text:list-item><text:p>list item one</text:p></text:list-item></text:list>
      <table:table>
        <table:table-row>
          <table:table-cell><text:p>cell_a</text:p></table:table-cell>
          <table:table-cell><text:p>cell_b</text:p></table:table-cell>
        </table:table-row>
      </table:table>
    </office:text>
  </office:body>
</office:document-content>''';
  await _writeOdfZip(file, contentXml, 'application/vnd.oasis.opendocument.text');
}

Future<void> writeMinimalOds(File file) async {
  final contentXml = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0">
  <office:body>
    <office:spreadsheet>
      <table:table table:name="Sheet1">
        <table:table-row>
          <table:table-cell><text:p>col_a</text:p></table:table-cell>
          <table:table-cell><text:p>col_b</text:p></table:table-cell>
        </table:table-row>
        <table:table-row>
          <table:table-cell><text:p>ods_value</text:p></table:table-cell>
          <table:table-cell><text:p>4</text:p></table:table-cell>
        </table:table-row>
      </table:table>
    </office:spreadsheet>
  </office:body>
</office:document-content>''';
  await _writeOdfZip(
    file,
    contentXml,
    'application/vnd.oasis.opendocument.spreadsheet',
  );
}

Future<void> writeMinimalOdp(File file) async {
  final contentXml = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0">
  <office:body>
    <office:presentation>
      <draw:page>
        <text:p>odp distinctive slide</text:p>
      </draw:page>
    </office:presentation>
  </office:body>
</office:document-content>''';
  await _writeOdfZip(
    file,
    contentXml,
    'application/vnd.oasis.opendocument.presentation',
  );
}

Future<void> writeMinimalParquet(File file, {String marker = 'parquet_marker_alpha'}) async {
  await withDuckDb((session) async {
    final path = file.absolute.path.replaceAll("'", "''");
    await session.queryRows(
      "COPY (SELECT '$marker' AS marker, 1 AS value UNION ALL SELECT 'row_two', 2) "
      "TO '$path' (FORMAT PARQUET)",
    );
  });
}

Future<void> writeLargeParquet(File file, int rowCount, {int? markerRow}) async {
  await withDuckDb((session) async {
    final path = file.absolute.path.replaceAll("'", "''");
    await session.queryRows(
      'CREATE TABLE tmp_rows AS SELECT '
      "CASE WHEN i = ${markerRow ?? -1} THEN 'format_parity_marker_row' ELSE 'row_' || i::VARCHAR END AS marker, "
      'i AS value '
      'FROM range($rowCount) t(i)',
    );
    await session.queryRows(
      "COPY tmp_rows TO '$path' (FORMAT PARQUET, ROW_GROUP_SIZE 32)",
    );
  });
}

Future<void> writeMalformedZip(File file) async {
  await file.writeAsBytes(utf8.encode('not a zip archive'));
}

Future<void> writeLargeCsv(File file, int rowCount, {String marker = 'Doe, John'}) async {
  final buffer = StringBuffer('name,value\n"$marker",42\n');
  for (var i = 0; i < rowCount; i++) {
    buffer.writeln('row$i,value$i');
  }
  await file.writeAsString(buffer.toString());
}

List<int> _buildPdf(List<String> objs) {
  final header = utf8.encode('%PDF-1.4\n');
  final bodyParts = <List<int>>[];
  final xrefPositions = <int>[];
  var pos = header.length;
  for (final obj in objs) {
    xrefPositions.add(pos);
    final chunk = utf8.encode(obj);
    bodyParts.add(chunk);
    pos += chunk.length;
  }
  final body = bodyParts.expand((part) => part).toList();
  final xrefStart = pos;
  final xrefLines = <String>[
    'xref\n',
    '0 ${objs.length + 1}\n',
    '0000000000 65535 f \n',
    for (final offset in xrefPositions) '${offset.toString().padLeft(10, '0')} 00000 n \n',
  ];
  final xref = utf8.encode(xrefLines.join());
  final trailer = utf8.encode(
    'trailer<< /Size ${objs.length + 1} /Root 1 0 R >>\n'
    'startxref\n$xrefStart\n%%EOF\n',
  );
  return [...header, ...body, ...xref, ...trailer];
}

Future<void> _writeOoxmlZip(File file, Map<String, String> entries) async {
  final archive = Archive();
  for (final entry in entries.entries) {
    archive.addFile(ArchiveFile.string(entry.key, entry.value));
  }
  final encoder = ZipEncoder();
  await file.writeAsBytes(encoder.encode(archive)!);
}

Future<void> _writeOdfZip(File file, String contentXml, String mimetype) async {
  final archive = Archive()
    ..addFile(ArchiveFile.string('mimetype', mimetype))
    ..addFile(ArchiveFile.string('content.xml', contentXml));
  final encoder = ZipEncoder();
  await file.writeAsBytes(encoder.encode(archive)!);
}

String _genericContentTypes() => '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
</Types>''';

String _contentTypesXml(String partName, String contentType) => '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="$partName" ContentType="$contentType"/>
</Types>''';
