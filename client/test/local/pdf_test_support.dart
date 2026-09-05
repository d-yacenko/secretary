import 'dart:io';

import 'package:pdfrx/pdfrx.dart';

bool _pdfInitialized = false;
bool? _pdfAvailable;

Future<bool> isPdfAvailableForTests() async {
  if (_pdfAvailable != null) {
    return _pdfAvailable!;
  }
  try {
    await configurePdfForTests();
    _pdfAvailable = true;
  } catch (_) {
    _pdfAvailable = false;
  }
  return _pdfAvailable!;
}

Future<void> configurePdfForTests() async {
  if (_pdfInitialized) {
    return;
  }
  await pdfrxInitialize(
    tmpPath: '${Directory.systemTemp.path}/pdfrx-test-cache',
  ).timeout(const Duration(seconds: 10));
  _pdfInitialized = true;
}
