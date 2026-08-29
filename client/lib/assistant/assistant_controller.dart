import 'package:flutter/foundation.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';

const int maxAssistantHistoryMessages = 12;

enum AssistantSendState {
  idle,
  sending,
  error,
}

class AssistantChatMessage {
  AssistantChatMessage({
    required this.role,
    required this.content,
    this.references = const [],
  });

  final String role;
  final String content;
  final List<AssistantReference> references;
}

class AssistantController extends ChangeNotifier {
  AssistantController({
    required SecretaryApiClient apiClient,
    required AuthController authController,
  })  : _apiClient = apiClient,
        _authController = authController;

  final SecretaryApiClient _apiClient;
  final AuthController _authController;

  final List<AssistantChatMessage> _messages = [];
  AssistantContextRef? _objectContext;
  AssistantContextRef? _notificationContext;
  AssistantSendState sendState = AssistantSendState.idle;
  String? errorMessage;
  String? _pendingRetryMessage;

  List<AssistantChatMessage> get messages => List.unmodifiable(_messages);
  AssistantContextRef? get objectContext => _objectContext;
  AssistantContextRef? get notificationContext => _notificationContext;
  String? get pendingRetryMessage => _pendingRetryMessage;
  bool get isSending => sendState == AssistantSendState.sending;

  void setObjectContext(SecretaryObject object) {
    _objectContext = AssistantContextRef(
      id: object.id,
      title: object.title,
      kind: object.kind,
    );
    _notificationContext = null;
    notifyListeners();
  }

  void setNotificationContext(NotificationOut notification) {
    _notificationContext = AssistantContextRef(
      id: notification.id,
      title: notification.title,
      kind: 'notification',
    );
    _objectContext = null;
    notifyListeners();
  }

  void clearObjectContext() {
    _objectContext = null;
    notifyListeners();
  }

  void clearNotificationContext() {
    _notificationContext = null;
    notifyListeners();
  }

  Future<void> sendMessage(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || sendState == AssistantSendState.sending) {
      return;
    }

    _pendingRetryMessage = trimmed;
    sendState = AssistantSendState.sending;
    errorMessage = null;
    notifyListeners();

    final history = _boundedHistory();
    try {
      final response = await _apiClient.sendAssistantMessage(
        AssistantMessageRequest(
          message: trimmed,
          history: history,
          contextObjectId: _objectContext?.id,
          contextNotificationId: _notificationContext?.id,
        ),
      );
      _messages.add(AssistantChatMessage(role: 'user', content: trimmed));
      _messages.add(
        AssistantChatMessage(
          role: 'assistant',
          content: response.answer,
          references: response.references,
        ),
      );
      _pendingRetryMessage = null;
      sendState = AssistantSendState.idle;
      notifyListeners();
    } on AuthenticationException catch (e) {
      sendState = AssistantSendState.error;
      errorMessage = e.message;
      _authController.handleAuthenticationFailure();
      notifyListeners();
    } on NetworkException catch (e) {
      sendState = AssistantSendState.error;
      errorMessage = e.message;
      notifyListeners();
    } on ApiException catch (e) {
      sendState = AssistantSendState.error;
      errorMessage = e.message;
      notifyListeners();
    }
  }

  List<AssistantHistoryMessage> _boundedHistory() {
    final pairs = <AssistantHistoryMessage>[];
    for (final message in _messages) {
      pairs.add(
        AssistantHistoryMessage(role: message.role, content: message.content),
      );
    }
    if (pairs.length > maxAssistantHistoryMessages) {
      return pairs.sublist(pairs.length - maxAssistantHistoryMessages);
    }
    return pairs;
  }

  void resetSession() {
    _messages.clear();
    _objectContext = null;
    _notificationContext = null;
    sendState = AssistantSendState.idle;
    errorMessage = null;
    _pendingRetryMessage = null;
    notifyListeners();
  }
}
