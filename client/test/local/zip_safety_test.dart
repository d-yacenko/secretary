import 'package:archive/archive.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/local/extraction/extraction_constants.dart';
import 'package:personal_secretary/local/extraction/zip_safety.dart';

void main() {
  test('rejects zip with too many entries', () {
    final archive = Archive();
    for (var i = 0; i <= kMaxOoxmlZipEntries; i++) {
      archive.addFile(ArchiveFile.string('entry_$i.txt', 'x'));
    }
    expect(
      () => validateZipArchive(archive),
      throwsA(isA<UnsafeZipError>()),
    );
  });

  test('rejects zip with excessive uncompressed size', () {
    final archive = Archive();
    final chunk = 'x' * (1024 * 1024);
    for (var i = 0; i < 33; i++) {
      archive.addFile(ArchiveFile.string('big_$i.txt', chunk));
    }
    expect(
      () => validateZipArchive(archive),
      throwsA(isA<UnsafeZipError>()),
    );
  });
}
