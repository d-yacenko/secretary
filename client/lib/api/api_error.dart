import 'dart:convert';

import 'package:http/http.dart' as http;

/// API failures surfaced to the UI without leaking credentials.
sealed class ApiException implements Exception {
  ApiException(this.message, {this.code});

  final String message;
  final String? code;

  @override
  String toString() => message;
}

class AuthenticationException extends ApiException {
  AuthenticationException([super.message = 'Authentication failed']);
}

class ValidationException extends ApiException {
  ValidationException(super.message, {this.fieldErrors = const {}, super.code});
  final Map<String, String> fieldErrors;
}

class NotFoundException extends ApiException {
  NotFoundException([super.message = 'Resource not found']);
}

class NetworkException extends ApiException {
  NetworkException([super.message = secretaryNetworkErrorMessage]);
}

class ServerException extends ApiException {
  ServerException([String message = 'Server error', String? code])
      : super(message, code: code);
}

const secretaryNetworkErrorMessage = 'Нет связи с сервером Секретаря.';

class ApiErrorDetail {
  const ApiErrorDetail({required this.message, this.code});

  final String message;
  final String? code;
}

ApiErrorDetail parseApiErrorDetail(http.Response response) {
  try {
    final decoded = jsonDecode(response.body);
    if (decoded is Map<String, dynamic>) {
      final detail = decoded['detail'];
      if (detail is String) {
        return ApiErrorDetail(message: detail);
      }
      if (detail is Map<String, dynamic>) {
        final code = detail['code'];
        final message = detail['message'];
        if (message is String) {
          return ApiErrorDetail(
            message: message,
            code: code is String ? code : null,
          );
        }
      }
      if (detail is List) {
        return ApiErrorDetail(
          message: detail.map((e) => e.toString()).join('; '),
        );
      }
    }
  } catch (_) {
    // ignore parse errors
  }
  return ApiErrorDetail(
    message: 'Request failed (${response.statusCode})',
  );
}
