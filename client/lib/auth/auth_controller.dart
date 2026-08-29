import 'package:flutter/foundation.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../config/url_utils.dart';
import 'server_url_store.dart';
import 'token_store.dart';

enum AuthStatus {
  initial,
  loading,
  authenticated,
  needsAuth,
  transientError,
}

class AuthController extends ChangeNotifier {
  AuthController({
    required SecretaryApiClient apiClient,
    required TokenStore tokenStore,
    required ServerUrlStore serverUrlStore,
    String? defaultBaseUrl,
  })  : _apiClient = apiClient,
        _tokenStore = tokenStore,
        _serverUrlStore = serverUrlStore,
        _defaultBaseUrl = defaultBaseUrl;

  final SecretaryApiClient _apiClient;
  final TokenStore _tokenStore;
  final ServerUrlStore _serverUrlStore;
  final String? _defaultBaseUrl;

  AuthStatus status = AuthStatus.initial;
  UserMe? user;
  String? serverUrl;
  String? errorMessage;

  SecretaryApiClient get apiClient => _apiClient;

  Future<void> initialize() async {
    status = AuthStatus.loading;
    errorMessage = null;
    notifyListeners();

    final storedUrl = await _serverUrlStore.readServerUrl();
    final resolvedUrl = normalizeBaseUrl(storedUrl ?? _defaultBaseUrl ?? '');
    serverUrl = resolvedUrl;

    final token = await _tokenStore.readToken();
    if (resolvedUrl == null || token == null || token.isEmpty) {
      status = AuthStatus.needsAuth;
      notifyListeners();
      return;
    }

    _apiClient.configure(baseUrl: resolvedUrl, token: token);
    try {
      user = await _apiClient.getMe();
      status = AuthStatus.authenticated;
    } on AuthenticationException {
      status = AuthStatus.needsAuth;
      errorMessage = 'Stored token is invalid. Enter a valid bearer token.';
    } on NetworkException catch (e) {
      status = AuthStatus.transientError;
      errorMessage = e.message;
    } on ApiException catch (e) {
      status = AuthStatus.transientError;
      errorMessage = e.message;
    }
    notifyListeners();
  }

  Future<bool> connect({
    required String serverUrlInput,
    required String token,
  }) async {
    final normalizedUrl = normalizeBaseUrl(serverUrlInput);
    if (normalizedUrl == null) {
      errorMessage = 'Enter a valid http or https server URL.';
      notifyListeners();
      return false;
    }
    final trimmedToken = token.trim();
    if (trimmedToken.isEmpty) {
      errorMessage = 'Bearer token is required.';
      notifyListeners();
      return false;
    }

    status = AuthStatus.loading;
    errorMessage = null;
    notifyListeners();

    _apiClient.configure(baseUrl: normalizedUrl, token: trimmedToken);
    try {
      final me = await _apiClient.getMe();
      await _serverUrlStore.writeServerUrl(normalizedUrl);
      await _tokenStore.writeToken(trimmedToken);
      serverUrl = normalizedUrl;
      user = me;
      status = AuthStatus.authenticated;
      notifyListeners();
      return true;
    } on AuthenticationException {
      _apiClient.clearToken();
      status = AuthStatus.needsAuth;
      errorMessage = 'Authentication failed. Check the bearer token.';
      notifyListeners();
      return false;
    } on NetworkException catch (e) {
      _apiClient.clearToken();
      status = AuthStatus.needsAuth;
      errorMessage = e.message;
      notifyListeners();
      return false;
    } on ApiException catch (e) {
      _apiClient.clearToken();
      status = AuthStatus.needsAuth;
      errorMessage = e.message;
      notifyListeners();
      return false;
    }
  }

  Future<void> forgetToken() async {
    await _tokenStore.deleteToken();
    _apiClient.clearToken();
    user = null;
    status = AuthStatus.needsAuth;
    errorMessage = null;
    notifyListeners();
  }

  void handleAuthenticationFailure() {
    status = AuthStatus.needsAuth;
    errorMessage = 'Session expired. Enter a valid bearer token.';
    notifyListeners();
  }
}
