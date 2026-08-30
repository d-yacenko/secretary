import 'package:flutter/material.dart';

import '../assistant/assistant_controller.dart';
import '../capture/capture_controller.dart';
import '../graph/graph_workspace_controller.dart';
import '../shell/app_shell.dart';
import 'auth_controller.dart';
import 'auth_setup_screen.dart';

/// Root home widget: swaps authenticated shell vs auth setup in-place.
class AuthGate extends StatelessWidget {
  const AuthGate({
    super.key,
    required this.authController,
    required this.captureController,
    required this.assistantController,
    required this.graphController,
  });

  final AuthController authController;
  final CaptureController captureController;
  final AssistantController assistantController;
  final GraphWorkspaceController graphController;

  @override
  Widget build(BuildContext context) {
    switch (authController.status) {
      case AuthStatus.initial:
      case AuthStatus.loading:
        return const Scaffold(
          body: Center(child: CircularProgressIndicator()),
        );
      case AuthStatus.authenticated:
        return AppShell(
          authController: authController,
          captureController: captureController,
          assistantController: assistantController,
          graphController: graphController,
        );
      case AuthStatus.needsAuth:
      case AuthStatus.transientError:
        return AuthSetupScreen(controller: authController);
    }
  }
}
