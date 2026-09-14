import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import '../auth/auth_controller.dart';
import '../auth/auth_setup_screen.dart';
import 'assistant_controller.dart';
import 'system_assistant_bridge.dart';
import 'voice_session_screen.dart';

/// Minimal lock-screen / overlay isolate. No Inbox or history.
class VoiceSessionApp extends StatefulWidget {
  const VoiceSessionApp({super.key, required this.authController});

  final AuthController authController;

  @override
  State<VoiceSessionApp> createState() => _VoiceSessionAppState();
}

class _VoiceSessionAppState extends State<VoiceSessionApp> {
  late final AssistantController _assistant;
  late final SystemAssistantController _systemAssistant;

  @override
  void initState() {
    super.initState();
    _assistant = AssistantController(
      apiClient: widget.authController.apiClient,
      authController: widget.authController,
      lockScreenSession: true,
    );
    _systemAssistant = SystemAssistantController();
    widget.authController.addListener(_onAuth);
    widget.authController.initialize();
    _syncAssistantGate();
  }

  void _onAuth() {
    _syncAssistantGate();
    setState(() {});
  }

  Future<void> _syncAssistantGate() async {
    await _systemAssistant.attach(widget.authController.user?.id);
    _assistant.keyguardLocked = _systemAssistant.keyguardLocked;
    _assistant.lockScreenVoiceEnabled = _systemAssistant.lockScreenVoiceEnabled;
  }

  @override
  void dispose() {
    widget.authController.removeListener(_onAuth);
    _assistant.dispose();
    _systemAssistant.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Секретарь',
      locale: const Locale('ru', 'RU'),
      supportedLocales: const [Locale('ru', 'RU')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
        useMaterial3: true,
      ),
      home: switch (widget.authController.status) {
        AuthStatus.initial || AuthStatus.loading => const Scaffold(
          body: Center(child: CircularProgressIndicator()),
        ),
        AuthStatus.authenticated => VoiceSessionScreen(
          assistant: _assistant,
          systemAssistant: _systemAssistant,
        ),
        AuthStatus.needsAuth || AuthStatus.transientError => AuthSetupScreen(
          controller: widget.authController,
        ),
      },
    );
  }
}
