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

  Uri? _baseUri;
  String? _token;

  String? get baseUrl => _baseUri?.toString();

  void configure({required String baseUrl, String? token}) {
    final normalized = parseApiBaseUrl(baseUrl);
    if (normalized == null) {
      throw ArgumentError('Invalid base URL');
    }
    _baseUri = normalized;
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

  Future<List<NotificationOut>> listUnresolvedNotifications() async {
    final body = await _request(
      'GET',
      '/notifications',
      queryParameters: {'status': 'unresolved'},
    );
    return (body['notifications'] as List<dynamic>)
        .map((e) => NotificationOut.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<NotificationOut> markNotificationRead(String notificationId) async {
    final body = await _request('POST', '/notifications/$notificationId/read');
    return NotificationOut.fromJson(body);
  }

  Future<NotificationOut> acceptNotification(String notificationId) async {
    final body = await _request('POST', '/notifications/$notificationId/accept');
    return NotificationOut.fromJson(body);
  }

  Future<NotificationOut> ignoreNotification(String notificationId) async {
    final body = await _request('POST', '/notifications/$notificationId/ignore');
    return NotificationOut.fromJson(body);
  }

  Future<TodayOut> getToday() async {
    final body = await _request('GET', '/today');
    return TodayOut.fromJson(body);
  }

  Future<SecretaryObject> getObject(String objectId) async {
    final body = await _request('GET', '/objects/$objectId');
    return SecretaryObject.fromJson(body);
  }

  Future<NeighborsResponse> getObjectNeighbors(String objectId) async {
    final body = await _request('GET', '/objects/$objectId/neighbors');
    return NeighborsResponse.fromJson(body);
  }

  Future<ContextResponse> getObjectContext(String objectId) async {
    final body = await _request('GET', '/objects/$objectId/context');
    return ContextResponse.fromJson(body);
  }

  Future<List<SecretaryObject>> searchObjects({
    required String query,
    String? kind,
    int limit = 20,
  }) async {
    final queryParameters = <String, String>{
      'q': query,
      'limit': '$limit',
    };
    if (kind != null && kind.isNotEmpty) {
      queryParameters['kind'] = kind;
    }
    final decoded = await _requestJson(
      'GET',
      '/search',
      queryParameters: queryParameters,
    );
    if (decoded is! List<dynamic>) {
      throw ServerException('Unexpected search response format');
    }
    return decoded
        .map((e) => SecretaryObject.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<AssistantMessageResponse> sendAssistantMessage(
    AssistantMessageRequest request,
  ) async {
    final body = await _request(
      'POST',
      '/assistant/message',
      jsonBody: request.toJson(),
    );
    return AssistantMessageResponse.fromJson(body);
  }

  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    Map<String, dynamic>? jsonBody,
    Map<String, String>? queryParameters,
    bool authenticated = true,
    Set<int> successStatuses = const {200},
  }) async {
    final decoded = await _requestJson(
      method,
      path,
      jsonBody: jsonBody,
      queryParameters: queryParameters,
      authenticated: authenticated,
      successStatuses: successStatuses,
    );
    if (decoded is Map<String, dynamic>) {
      return decoded;
    }
    throw ServerException('Unexpected response format');
  }

  Future<dynamic> _requestJson(
    String method,
    String path, {
    Map<String, dynamic>? jsonBody,
    Map<String, String>? queryParameters,
    bool authenticated = true,
    Set<int> successStatuses = const {200},
  }) async {
    if (_baseUri == null) {
      throw StateError('API client is not configured with a base URL');
    }
    if (authenticated && (_token == null || _token!.isEmpty)) {
      throw AuthenticationException();
    }

    final uri = buildApiEndpointUri(_baseUri!, path).replace(
      queryParameters: queryParameters,
    );
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

  dynamic _mapResponse(
    http.Response response,
    Set<int> successStatuses,
  ) {
    if (successStatuses.contains(response.statusCode)) {
      if (response.body.isEmpty) {
        return {};
      }
      final decoded = jsonDecode(response.body);
      return decoded;
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
