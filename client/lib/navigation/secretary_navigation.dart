import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../capture/capture_screen.dart';
import '../objects/object_detail_screen.dart';

Future<void> openObjectDetail(
  BuildContext context, {
  required String objectId,
  required SecretaryApiClient apiClient,
  required AuthController authController,
  required CaptureController captureController,
}) async {
  await Navigator.of(context).push<void>(
    MaterialPageRoute<void>(
      builder: (context) => ObjectDetailScreen(
        objectId: objectId,
        apiClient: apiClient,
        authController: authController,
        captureController: captureController,
      ),
    ),
  );
}

Future<void> openNotificationContext(
  BuildContext context, {
  required NotificationOut notification,
  required SecretaryApiClient apiClient,
  required AuthController authController,
  required CaptureController captureController,
}) async {
  try {
    if (notification.status == 'new') {
      await apiClient.markNotificationRead(notification.id);
    }
  } on AuthenticationException {
    authController.handleAuthenticationFailure();
    return;
  } catch (_) {
    // best effort read
  }

  final objectId = notification.sourceObjectId ??
      notification.relatedObjectId ??
      notification.resultObjectId;

  if (objectId != null) {
    if (!context.mounted) {
      return;
    }
    await openObjectDetail(
      context,
      objectId: objectId,
      apiClient: apiClient,
      authController: authController,
      captureController: captureController,
    );
    return;
  }

  if (!context.mounted) {
    return;
  }

  await showDialog<void>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(notification.title),
      content: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Priority: ${notification.priority}'),
            if (notification.proposalType != null)
              Text('Proposal: ${notification.proposalType}'),
            if (notification.proposalDescription != null)
              Text(notification.proposalDescription!),
            if (notification.proposedAction != null)
              Text('Action: ${notification.proposedAction}'),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
      ],
    ),
  );
}

Future<void> openCapture(
  BuildContext context, {
  required CaptureController captureController,
}) async {
  await Navigator.of(context).push<void>(
    MaterialPageRoute<void>(
      builder: (context) => CaptureScreen(controller: captureController),
    ),
  );
}
