import 'dart:io';

import 'package:archive/archive.dart';
import 'package:archive/archive_io.dart';
import 'package:xml/xml.dart';

import 'zip_safety.dart';

Future<Archive> readZipArchive(File file) async {
  final input = InputFileStream(file.path);
  try {
    final archive = ZipDecoder().decodeStream(input);
    validateZipArchive(archive);
    return archive;
  } finally {
    await input.close();
  }
}

List<int> readArchiveEntry(Archive archive, String name) {
  final file = archive.find(name);
  if (file == null || !file.isFile) {
    throw FormatException('missing archive entry: $name');
  }
  return file.content;
}

XmlDocument parseSafeXml(List<int> bytes) {
  return XmlDocument.parse(String.fromCharCodes(bytes));
}

String elementText(XmlElement element) => element.innerText.trim();

String escapeSqlString(String value) => value.replaceAll("'", "''");
