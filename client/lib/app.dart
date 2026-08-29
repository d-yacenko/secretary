import 'package:flutter/material.dart';

import 'auth/auth_controller.dart';
import 'auth/auth_setup_screen.dart';
import 'capture/capture_controller.dart';
import 'shell/app_shell.dart';

class PersonalSecretaryApp extends StatefulWidget {
  const PersonalSecretaryApp({super.key, required this.authController});

  final AuthController authController;

  @override
  State<PersonalSecretaryApp> createState() => _PersonalSecretaryAppState();
}

class _PersonalSecretaryAppState extends State<PersonalSecretaryApp> {
  late final CaptureController _captureController;

  @override
  void initState() {
    super.initState();
    _captureController = CaptureController(
      apiClient: widget.authController.apiClient,
      authController: widget.authController,
    );
    widget.authController.addListener(_onAuthChanged);
    widget.authController.initialize();
  }

  void _onAuthChanged() {
    setState(() {});
  }

  @override
  void dispose() {
    widget.authController.removeListener(_onAuthChanged);
    _captureController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final auth = widget.authController;

    Widget home;
    switch (auth.status) {
      case AuthStatus.initial:
      case AuthStatus.loading:
        home = const Scaffold(
          body: Center(child: CircularProgressIndicator()),
        );
      case AuthStatus.authenticated:
        home = AppShell(
          authController: auth,
          captureController: _captureController,
        );
      case AuthStatus.needsAuth:
      case AuthStatus.transientError:
        home = AuthSetupScreen(controller: auth);
    }

    return MaterialApp(
      title: 'Personal Secretary',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
        useMaterial3: true,
      ),
      home: home,
    );
  }
}
