import 'package:flutter/material.dart';

import 'auth/auth_controller.dart';
import 'auth/auth_gate.dart';
import 'capture/capture_controller.dart';

class PersonalSecretaryApp extends StatefulWidget {
  const PersonalSecretaryApp({super.key, required this.authController});

  final AuthController authController;

  @override
  State<PersonalSecretaryApp> createState() => _PersonalSecretaryAppState();
}

class _PersonalSecretaryAppState extends State<PersonalSecretaryApp> {
  final _navigatorKey = GlobalKey<NavigatorState>();
  late final AuthSessionNavigator _authSessionNavigator;
  late final CaptureController _captureController;

  @override
  void initState() {
    super.initState();
    _authSessionNavigator = AuthSessionNavigator(_navigatorKey);
    _captureController = CaptureController(
      apiClient: widget.authController.apiClient,
      authController: widget.authController,
    );
    widget.authController.onSessionTerminated = _onSessionTerminated;
    widget.authController.addListener(_onAuthChanged);
    widget.authController.initialize();
  }

  void _onSessionTerminated() {
    _captureController.resetSession();
    _authSessionNavigator.resetNavigationStack();
  }

  void _onAuthChanged() {
    setState(() {});
  }

  @override
  void dispose() {
    widget.authController.onSessionTerminated = null;
    widget.authController.removeListener(_onAuthChanged);
    _captureController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      navigatorKey: _navigatorKey,
      title: 'Personal Secretary',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
        useMaterial3: true,
      ),
      home: AuthGate(
        authController: widget.authController,
        captureController: _captureController,
      ),
    );
  }
}
