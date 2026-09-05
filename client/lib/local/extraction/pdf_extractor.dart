import 'dart:io';

import 'package:syncfusion_flutter_pdf/pdf.dart';

import 'extraction_constants.dart';
import 'representation_builder.dart';

class PdfExtractionResult {
  const PdfExtractionResult({
    required this.representations,
    this.userMessage,
    this.extractionFailed = false,
    this.metadataOnly = false,
  });

  final List<Map<String, dynamic>> representations;
  final String? userMessage;
  final bool extractionFailed;
  final bool metadataOnly;
}

Future<PdfExtractionResult> extractPdfFile(File file) async {
  final bytes = await file.readAsBytes();
  PdfDocument? document;
  try {
    document = PdfDocument(inputBytes: bytes);
    final pageCount = document.pages.count;
    final truncated = pageCount > kMaxPdfPages;
    final lastPage = pageCount < kMaxPdfPages ? pageCount : kMaxPdfPages;
    final parts = <String>[];
    for (var pageIndex = 0; pageIndex < lastPage; pageIndex++) {
      final pageText = PdfTextExtractor(document)
          .extractText(startPageIndex: pageIndex, endPageIndex: pageIndex)
          .trim();
      if (pageText.isNotEmpty) {
        parts.add('[page ${pageIndex + 1}]\n$pageText');
      }
    }
    if (parts.isEmpty) {
      return const PdfExtractionResult(
        representations: [],
        metadataOnly: true,
        userMessage: 'В PDF нет извлекаемого текста',
      );
    }
    return PdfExtractionResult(
      representations: buildTextRepresentations(
        parts.join('\n\n'),
        metadata: {
          'page_count': lastPage,
          'page_truncated': truncated,
        },
      ),
    );
  } catch (error) {
    final message = error.toString().toLowerCase();
    if (message.contains('password') || message.contains('encrypt')) {
      return const PdfExtractionResult(
        representations: [],
        metadataOnly: true,
        extractionFailed: true,
        userMessage: 'PDF зашифрован; извлечение текста недоступно',
      );
    }
    return const PdfExtractionResult(
      representations: [],
      metadataOnly: true,
      extractionFailed: true,
      userMessage: 'Не удалось прочитать PDF',
    );
  } finally {
    document?.dispose();
  }
}
