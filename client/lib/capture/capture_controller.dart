import 'package:flutter/foundation.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';
import 'capture_draft.dart';

enum CaptureSubmitState {
  idle,
  submitting,
  success,
  validationError,
  authError,
  networkError,
  serverError,
}

class CaptureController extends ChangeNotifier {
  CaptureController({
    required SecretaryApiClient apiClient,
    required AuthController authController,
    CaptureDraft? initialDraft,
  })  : _apiClient = apiClient,
        _authController = authController,
        _draft = initialDraft ?? CaptureDraft.empty;

  final SecretaryApiClient _apiClient;
  final AuthController _authController;

  CaptureDraft _draft;
  CaptureSubmitState submitState = CaptureSubmitState.idle;
  String? errorMessage;
  CaptureTaskResponse? lastResult;

  CaptureDraft get draft => _draft;

  void setText(String value) {
    _draft = _draft.copyWith(text: value);
    if (submitState != CaptureSubmitState.submitting) {
      submitState = CaptureSubmitState.idle;
      errorMessage = null;
    }
    notifyListeners();
  }

  void setTitle(String? value) {
    final trimmed = value?.trim();
    _draft = trimmed == null || trimmed.isEmpty
        ? _draft.copyWith(clearTitle: true)
        : _draft.copyWith(title: value);
    if (submitState != CaptureSubmitState.submitting) {
      submitState = CaptureSubmitState.idle;
      errorMessage = null;
    }
    notifyListeners();
  }

  void mergeDraft(CaptureDraft draft) {
    _draft = draft;
    submitState = CaptureSubmitState.idle;
    errorMessage = null;
    notifyListeners();
  }

  Future<void> submit() async {
    if (!_draft.canSubmit || submitState == CaptureSubmitState.submitting) {
      if (_draft.isBlank) {
        submitState = CaptureSubmitState.validationError;
        errorMessage = 'Task text cannot be blank.';
        notifyListeners();
      }
      return;
    }

    submitState = CaptureSubmitState.submitting;
    errorMessage = null;
    notifyListeners();

    try {
      final result = await _apiClient.captureTask(_draft.toRequest());
      lastResult = result;
      _draft = CaptureDraft.empty;
      submitState = CaptureSubmitState.success;
      notifyListeners();
    } on AuthenticationException catch (e) {
      submitState = CaptureSubmitState.authError;
      errorMessage = e.message;
      _authController.handleAuthenticationFailure();
      notifyListeners();
    } on ValidationException catch (e) {
      submitState = CaptureSubmitState.validationError;
      errorMessage = e.message;
      notifyListeners();
    } on NetworkException catch (e) {
      submitState = CaptureSubmitState.networkError;
      errorMessage = e.message;
      notifyListeners();
    } on ApiException catch (e) {
      submitState = CaptureSubmitState.serverError;
      errorMessage = e.message;
      notifyListeners();
    }
  }

  void clearSuccess() {
    if (submitState == CaptureSubmitState.success) {
      submitState = CaptureSubmitState.idle;
      notifyListeners();
    }
  }
}
