/// API failures surfaced to the UI without leaking credentials.
sealed class ApiException implements Exception {
  ApiException(this.message);
  final String message;

  @override
  String toString() => message;
}

class AuthenticationException extends ApiException {
  AuthenticationException([super.message = 'Authentication failed']);
}

class ValidationException extends ApiException {
  ValidationException(super.message, {this.fieldErrors = const {}});
  final Map<String, String> fieldErrors;
}

class NotFoundException extends ApiException {
  NotFoundException([super.message = 'Resource not found']);
}

class NetworkException extends ApiException {
  NetworkException([super.message = 'Network error']);
}

class ServerException extends ApiException {
  ServerException([super.message = 'Server error']);
}
