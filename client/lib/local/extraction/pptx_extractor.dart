import 'dart:io';

import 'package:archive/archive.dart';
import 'package:xml/xml.dart';

import 'archive_xml_utils.dart';
import 'extraction_constants.dart';
import 'representation_builder.dart';

const _pptxNs = 'http://schemas.openxmlformats.org/drawingml/2006/main';

Future<List<Map<String, dynamic>>> extractPptxFile(File file) async {
  final archive = await readZipArchive(file);
  final slidePaths = archive.files
      .map((entry) => entry.name)
      .where(
        (name) => name.startsWith('ppt/slides/slide') && name.endsWith('.xml'),
      )
      .toList()
    ..sort();
  final truncated = slidePaths.length > kMaxPptxSlides;
  final selected = slidePaths.take(kMaxPptxSlides).toList();
  final lines = <String>[];
  for (var index = 0; index < selected.length; index++) {
    final slidePath = selected[index];
    final root =
        parseSafeXml(readArchiveEntry(archive, slidePath)).rootElement;
    final texts = root
        .descendants
        .whereType<XmlElement>()
        .where(
          (element) =>
              element.name.local == 't' &&
              element.name.namespaceUri == _pptxNs,
        )
        .map((node) => node.innerText.trim())
        .where((text) => text.isNotEmpty)
        .toList();
    lines.add('[slide ${index + 1}]');
    lines.addAll(texts);
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
