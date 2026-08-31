import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/local/local_resource_extractor.dart';

void main() {
  late Directory tempDir;
  late LocalResourceExtractor extractor;

  setUp(() {
    tempDir = Directory.systemTemp.createTempSync('extractor-test-');
    extractor = LocalResourceExtractor();
  });

  tearDown(() {
    if (tempDir.existsSync()) {
      tempDir.deleteSync(recursive: true);
    }
  });

  File writeFile(String name, String content) {
    final file = File('${tempDir.path}/$name');
    file.writeAsStringSync(content);
    return file;
  }

  test('small txt produces full representation', () {
    final file = writeFile('small.txt', 'short text');
    final result = extractor.extractFile(file);
    expect(result.metadataOnly, isFalse);
    expect(result.representations.single['kind'], 'full');
  });

  test('large txt produces bounded chunks', () {
    final file = writeFile('large.txt', 'word ' * 5000);
    final result = extractor.extractFile(file);
    expect(result.metadataOnly, isFalse);
    expect(result.representations.every((r) => r['kind'] == 'chunk'), isTrue);
    expect(result.representations.length <= kMaxExtractorParts, isTrue);
  });

  test('md treated as text', () {
    final file = writeFile('note.md', '# Title\n\nBody');
    final result = extractor.extractFile(file);
    expect(result.suggestedKind, 'document');
    expect(result.representations.isNotEmpty, isTrue);
  });

  test('csv produces schema sample statistics', () {
    final file = writeFile('data.csv', 'a,b\n1,2\n3,4');
    final result = extractor.extractFile(file);
    final kinds = result.representations.map((r) => r['kind']).toSet();
    expect(kinds.contains('schema'), isTrue);
    expect(kinds.contains('sample'), isTrue);
    expect(kinds.contains('statistics'), isTrue);
  });

  test('unsupported file is metadata-only', () {
    final file = writeFile('doc.pdf', '%PDF-1.4');
    final result = extractor.extractFile(file);
    expect(result.metadataOnly, isTrue);
    expect(result.representations, isEmpty);
  });

  test('revision stable for unchanged file', () {
    final file = writeFile('stable.txt', 'same');
    final first = extractor.extractFile(file);
    final second = extractor.extractFile(file);
    expect(first.contentRevision, second.contentRevision);
  });

  test('changed content changes revision', () {
    final file = writeFile('change.txt', 'one');
    final first = extractor.extractFile(file);
    file.writeAsStringSync('two');
    final second = extractor.extractFile(file);
    expect(first.contentRevision, isNot(second.contentRevision));
  });
}
