import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'api_error.dart';
import 'api_models.dart';
import '../config/url_utils.dart';

/// Typed HTTP client for Secretary personal APIs.
class SecretaryApiClient {
  SecretaryApiClient({http.Client? httpClient, Duration? timeout})
      : _httpClient = httpClient ?? http.Client(),
        _timeout = timeout ?? const Duration(seconds: 30);

  final http.Client _httpClient;
  final Duration _timeout;

  String? _baseUrl;
  String? _token;

  String? get baseUrl => _baseUrl;
  String? get token => _token;

  void configure({required String baseUrl, String? token}) {
    final normalized = normalizeBaseUrl(baseUrl);
    if (normalized == null) {
      throw ArgumentError('Invalid base URL');
    }
    _baseUrl = normalized;
    _token = token;
  }

  void clearToken() {
    _token = null;
  }

  Future<HealthStatus> getHealth() async {
    final body = await _request('GET', '/health', authenticated: false);
    return HealthStatus.fromJson(body);
  }

  Future<UserMe> getMe() async {
    final body = await _request('GET', '/me');
    return UserMe.fromJson(body);
  }

  Future<Connections> getConnections() async {
    final body = await _request('GET', '/connections');
    return Connections.fromJson(body);
  }

  Future<CaptureTaskResponse> captureTask(CaptureTaskRequest request) async {
    final body = await _request(
      'POST',
      '/capture/task',
      jsonBody: request.toJson(),
      successStatuses: {201},
    );
    return CaptureTaskResponse.fromJson(body);
  }

  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    Map<String, dynamic>? jsonBody,
    bool authenticated = true,
    Set<int> successStatuses = const {200},
  }) async {
    if (_baseUrl == null) {
      throw StateError('API client is not configured with a base URL');
    }
    if (authenticated && (_token == null || _token!.isEmpty)) {
      throw AuthenticationException();
    }

    final uri = _buildUri(path);
    final headers = <String, String>{
      'Accept': 'application/json',
      if (jsonBody != null) 'Content-Type': 'application/json',
      if (authenticated && _token != null) 'Authorization': 'Bearer $_token',
    };

    try {
      final response = await _httpClient
          .send(
            http.Request(method, uri)
              ..headers.addAll(headers)
              ..body = jsonBody == null ? '' : jsonEncode(jsonBody),
          )
          .timeout(_timeout)
          .then(http.Response.fromStream);

      return _mapResponse(response, successStatuses);
    } on TimeoutException {
      throw NetworkException('Request timed out');
    } on http.ClientException catch (e) {
      throw NetworkException(sanitizeErrorMessage(e.message));
    }
  }

  Uri _buildUri(String path) {
    final normalizedPath = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$_baseUrl$normalizedPath');
  }

  Map<String, dynamic> _mapResponse(
    http.Response response,
    Set<int> successStatuses,
  ) {
    if (successStatuses.contains(response.statusCode)) {
      if (response.body.isEmpty) {
        return {};
      }
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }
      throw ServerException('Unexpected response format');
    }

    final detail = _extractDetail(response);
    final safeMessage = sanitizeErrorMessage(detail);

    switch (response.statusCode) {
      case 401:
        throw AuthenticationException(safeMessage);
      case 404:
        throw NotFoundException(safeMessage);
      case 422:
        throw ValidationException(safeMessage);
      default:
        if (response.statusCode >= 500) {
          throw ServerException(safeMessage);
        }
        throw ServerException(safeMessage);
    }
  }

  String _extractDetail(http.Response response) {
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) {
        final detail = decoded['detail'];
        if (detail is String) {
          return detail;
        }
        if (detail is List) {
          return detail.map((e) => e.toString()).join('; ');
        }
      }
    } catch (_) {
      // ignore parse errors
    }
    return 'Request failed (${response.statusCode})';
  }

  /// Removes bearer tokens from error text so they never appear in UI/logs.
  static String sanitizeErrorMessage(String message) {
    if (message.isEmpty) {
      return 'Request failed';
    }
    final bearerPattern = RegExp(
      r'Bearer\s+[A-Za-z0-9._\-+/=]+',
      caseSensitive: false,
    );
    return message.replaceAll(bearerPattern, 'Bearer [redacted]');
  }
}
