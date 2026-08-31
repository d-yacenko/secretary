import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/local/client_content_revision.dart';
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

  test('revision matches backend algorithm', () {
    final file = writeFile('align.txt', 'payload');
    final result = extractor.extractFile(file);
    final expected = computeClientContentRevision(
      clientSourceLocator: file.path,
      size: result.size,
      modifiedAt: result.modifiedAt,
      contentHash: result.contentHash,
    );
    expect(result.contentRevision, expected);
  });

  test('utf8 byte bounds per part', () {
    final file = writeFile('bytes.txt', 'й' * 20000);
    final result = extractor.extractFile(file);
    for (final rep in result.representations) {
      expect(utf8ByteLength(rep['text'] as String), lessThanOrEqualTo(kMaxExtractorPartBytes));
    }
  });

  test('aggregate utf8 byte bound', () {
    final file = writeFile('aggregate.txt', 'word ' * 10000);
    final result = extractor.extractFile(file);
    var total = 0;
    for (final rep in result.representations) {
      total += utf8ByteLength(rep['text'] as String);
    }
    expect(total, lessThanOrEqualTo(kMaxExtractorTotalBytes));
  });

  test('whitespace-heavy text stays bounded', () {
    final file = writeFile('spaces.txt', ' ' * 50000);
    final result = extractor.extractFile(file);
    expect(result.representations.length <= kMaxExtractorParts, isTrue);
    for (final rep in result.representations) {
      expect(utf8ByteLength(rep['text'] as String), lessThanOrEqualTo(kMaxExtractorPartBytes));
    }
  });

  test('quoted csv comma parsed', () {
    final file = writeFile('quoted.csv', 'name,value\n"Doe, John",42\n"Smith",17');
    final result = extractor.extractFile(file);
    final sample = result.representations.firstWhere((r) => r['kind'] == 'sample');
    expect(sample['text'], contains('Doe, John'));
  });

  test('escaped quote csv parsed', () {
    final file = writeFile('escape.csv', 'name,note\n"John","said ""hi"""');
    final result = extractor.extractFile(file);
    final sample = result.representations.firstWhere((r) => r['kind'] == 'sample');
    expect(sample['text'], contains('said'));
  });

  test('empty csv cell preserved', () {
    final file = writeFile('empty.csv', 'a,b\n,2');
    final result = extractor.extractFile(file);
    final sample = result.representations.firstWhere((r) => r['kind'] == 'sample');
    expect(sample['text'], isNotEmpty);
  });

  test('utf8 csv values', () {
    final file = writeFile('utf8.csv', 'name,value\nМосква,42');
    final result = extractor.extractFile(file);
    final sample = result.representations.firstWhere((r) => r['kind'] == 'sample');
    expect(sample['text'], contains('Москва'));
  });

  test('large csv uses coherent prefix without mid-file splice', () {
    final rows = <String>['name,value', '"Doe, John",42'];
    rows.addAll(List.generate(20000, (i) => 'row$i,value$i'));
    final file = writeFile('huge.csv', rows.join('\n'));
    final result = extractor.extractFile(file);
    final sample = result.representations.firstWhere((r) => r['kind'] == 'sample');
    expect(sample['text'], contains('Doe, John'));
    expect(sample['text'], isNot(contains('row19999')));
  });
}
