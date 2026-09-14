import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import '../auth/auth_controller.dart';
import '../auth/auth_setup_screen.dart';
import 'assistant_controller.dart';
import 'system_assistant_bridge.dart';
import 'voice_session_screen.dart';

/// Minimal lock-screen / overlay isolate. No Inbox or history.
class VoiceSessionApp extends StatefulWidget {
  const VoiceSessionApp({
    super.key,
    required this.authController,
    this.assistant,
    this.systemAssistant,
  });

  final AuthController authController;
  final AssistantController? assistant;
  final SystemAssistantController? systemAssistant;

  @override
  State<VoiceSessionApp> createState() => _VoiceSessionAppState();
}

class _VoiceSessionAppState extends State<VoiceSessionApp> {
  late final AssistantController _assistant;
  late final SystemAssistantController _systemAssistant;
  late final bool _ownsAssistant;
  late final bool _ownsSystemAssistant;
  var _gateReady = false;

  @override
  void initState() {
    super.initState();
    _ownsAssistant = widget.assistant == null;
    _ownsSystemAssistant = widget.systemAssistant == null;
    _assistant =
        widget.assistant ??
        AssistantController(
          apiClient: widget.authController.apiClient,
          authController: widget.authController,
          lockScreenSession: true,
        );
    _systemAssistant = widget.systemAssistant ?? SystemAssistantController();
    widget.authController.addListener(_onAuth);
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    await widget.authController.initialize();
    if (!mounted) {
      return;
    }
    await _systemAssistant.attach(widget.authController.user?.id);
    if (!mounted) {
      return;
    }
    _assistant.keyguardLocked = _systemAssistant.keyguardLocked;
    _assistant.lockScreenVoiceEnabled = _systemAssistant.lockScreenVoiceEnabled;
    setState(() {
      _gateReady = true;
    });
  }

  void _onAuth() {
    if (!_gateReady) {
      if (mounted) {
        setState(() {});
      }
      return;
    }
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
    if (_ownsAssistant) {
      _assistant.dispose();
    }
    if (_ownsSystemAssistant) {
      _systemAssistant.dispose();
    }
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
      home:
          !_gateReady ||
              widget.authController.status == AuthStatus.initial ||
              widget.authController.status == AuthStatus.loading
          ? const Scaffold(body: Center(child: CircularProgressIndicator()))
          : switch (widget.authController.status) {
              AuthStatus.authenticated => VoiceSessionScreen(
                assistant: _assistant,
                systemAssistant: _systemAssistant,
              ),
              AuthStatus.needsAuth || AuthStatus.transientError =>
                AuthSetupScreen(controller: widget.authController),
              AuthStatus.initial || AuthStatus.loading => const Scaffold(
                body: Center(child: CircularProgressIndicator()),
              ),
            },
    );
  }
}
