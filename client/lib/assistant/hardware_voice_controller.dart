import 'dart:async';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';

import '../auth/auth_controller.dart';
import 'hardware_voice_binding.dart';
import 'hardware_voice_bridge.dart';
import 'hardware_voice_keys.dart';
import 'hardware_voice_store.dart';

enum HardwareVoiceUiPhase { idle, learning, testing }

class HardwareVoiceController extends ChangeNotifier {
  HardwareVoiceController({
    required AuthController authController,
    HardwareVoiceStore? store,
    HardwareVoiceBridge? bridge,
  }) : _authController = authController,
       _store = store ?? HardwareVoiceStore(),
       _bridge =
           bridge ??
           (!kIsWeb && Platform.isAndroid
               ? MethodChannelHardwareVoiceBridge()
               : NoopHardwareVoiceBridge()) {
    _bridge.setListener(
      HardwareVoiceBridgeListener(
        onVoiceTrigger: _onNativeVoiceTrigger,
        onLearnResult: _onNativeLearnResult,
        onTestResult: _onNativeTestResult,
      ),
    );
    _authController.addListener(_onAuthChanged);
  }

  final AuthController _authController;
  final HardwareVoiceStore _store;
  final HardwareVoiceBridge _bridge;

  HardwareVoiceBinding? _binding;
  HardwareVoiceUiPhase _phase = HardwareVoiceUiPhase.idle;
  Completer<HardwareVoiceLearnResult>? _learnCompleter;
  Completer<HardwareVoiceTestResult>? _testCompleter;
  String? _activeUserId;
  String? _learnHint;

  /// AppShell sets this to switch to Assistant and invoke the canonical trigger.
  /// Return true if the trigger was accepted by the shell (foreground main route).
  Future<bool> Function()? onShellVoiceTrigger;

  HardwareVoiceBinding? get binding => _binding;
  HardwareVoiceUiPhase get phase => _phase;
  bool get hasEnabledBinding => _binding != null && _binding!.enabled;
  bool get isLearning => _phase == HardwareVoiceUiPhase.learning;
  bool get isTesting => _phase == HardwareVoiceUiPhase.testing;
  String? get learnHint => _learnHint;

  String get statusPrimary =>
      hasEnabledBinding ? _binding!.statusPrimary : 'Не настроена';

  String? get statusSecondary =>
      hasEnabledBinding ? _binding!.statusSecondary : null;

  Future<void> attach() async {
    await _syncFromAuth();
  }

  Future<void> useVolumeUpDouble() async {
    await _saveAndConfigure(HardwareVoiceBinding.volumeUpDouble());
  }

  Future<void> saveLearned({
    required int keyCode,
    int scanCode = 0,
    String? androidKeyName,
  }) async {
    await _saveAndConfigure(
      HardwareVoiceBinding.learned(
        keyCode: keyCode,
        scanCode: scanCode,
        androidKeyName: androidKeyName,
      ),
    );
  }

  Future<void> setGesture(HardwareVoiceGesture gesture) async {
    final current = _binding;
    if (current == null || !current.enabled) {
      return;
    }
    if (current.isVolumeUp) {
      await _saveAndConfigure(HardwareVoiceBinding.volumeUpDouble());
      return;
    }
    await _saveAndConfigure(current.copyWith(gesture: gesture));
  }

  Future<void> disable() async {
    final userId = _authController.user?.id;
    _binding = null;
    if (userId != null) {
      await _store.clear(userId);
    }
    await _disableNative();
    notifyListeners();
  }

  Future<HardwareVoiceLearnResult> startLearn({
    int timeoutMs = hardwareVoiceLearnTimeoutMs,
  }) async {
    if (_phase != HardwareVoiceUiPhase.idle) {
      return const HardwareVoiceLearnResult(
        status: HardwareVoiceLearnStatus.cancelled,
      );
    }
    _phase = HardwareVoiceUiPhase.learning;
    _learnHint = null;
    final completer = Completer<HardwareVoiceLearnResult>();
    _learnCompleter = completer;
    notifyListeners();
    try {
      await _bridge.startLearn(timeoutMs: timeoutMs);
    } catch (error) {
      _phase = HardwareVoiceUiPhase.idle;
      if (!completer.isCompleted) {
        completer.complete(
          HardwareVoiceLearnResult(
            status: HardwareVoiceLearnStatus.timeout,
            message: error.toString(),
          ),
        );
      }
      _learnCompleter = null;
      notifyListeners();
      return completer.future;
    }
    return completer.future;
  }

  Future<void> cancelLearn() async {
    if (_phase != HardwareVoiceUiPhase.learning) {
      return;
    }
    await _bridge.cancelLearn();
  }

  Future<HardwareVoiceTestResult> startTest({
    int timeoutMs = hardwareVoiceLearnTimeoutMs,
  }) async {
    if (!hasEnabledBinding || _phase != HardwareVoiceUiPhase.idle) {
      return const HardwareVoiceTestResult(
        status: HardwareVoiceTestStatus.cancelled,
      );
    }
    _phase = HardwareVoiceUiPhase.testing;
    final completer = Completer<HardwareVoiceTestResult>();
    _testCompleter = completer;
    notifyListeners();
    try {
      await _bridge.startTest(timeoutMs: timeoutMs);
    } catch (error) {
      _phase = HardwareVoiceUiPhase.idle;
      if (!completer.isCompleted) {
        completer.complete(
          const HardwareVoiceTestResult(
            status: HardwareVoiceTestStatus.timeout,
          ),
        );
      }
      _testCompleter = null;
      notifyListeners();
      return completer.future;
    }
    return completer.future;
  }

  Future<void> cancelTest() async {
    if (_phase != HardwareVoiceUiPhase.testing) {
      return;
    }
    await _bridge.cancelTest();
  }

  /// Used by tests to simulate a native armed trigger.
  @visibleForTesting
  void debugEmitVoiceTrigger() {
    _onNativeVoiceTrigger();
  }

  @visibleForTesting
  void debugEmitLearnResult(HardwareVoiceLearnResult result) {
    _onNativeLearnResult(result);
  }

  @visibleForTesting
  void debugEmitTestResult(HardwareVoiceTestResult result) {
    _onNativeTestResult(result);
  }

  Future<void> _onAuthChanged() async {
    await _syncFromAuth();
  }

  Future<void> _syncFromAuth() async {
    final user = _authController.user;
    final authenticated = _authController.status == AuthStatus.authenticated;
    if (!authenticated || user == null) {
      _activeUserId = null;
      _binding = null;
      _abortSessions();
      await _disableNative();
      notifyListeners();
      return;
    }
    if (_activeUserId == user.id && _binding != null) {
      await _configureNative(_binding!);
      return;
    }
    _activeUserId = user.id;
    _binding = await _store.load(user.id);
    if (_binding != null && _binding!.enabled) {
      await _configureNative(_binding!);
    } else {
      await _disableNative();
    }
    notifyListeners();
  }

  Future<void> _saveAndConfigure(HardwareVoiceBinding binding) async {
    final userId = _authController.user?.id;
    final normalized = binding.normalized();
    _binding = normalized;
    if (userId != null) {
      await _store.save(userId, normalized);
    }
    if (normalized.enabled) {
      await _configureNative(normalized);
    } else {
      await _disableNative();
    }
    notifyListeners();
  }

  Future<void> _configureNative(HardwareVoiceBinding binding) async {
    await _bridge.configure(
      HardwareVoiceNativeConfig(
        enabled: binding.enabled,
        keyCode: binding.keyCode,
        scanCode: binding.scanCode,
        gesture: binding.gesture,
      ),
    );
  }

  Future<void> _disableNative() async {
    await _bridge.configure(
      const HardwareVoiceNativeConfig(
        enabled: false,
        keyCode: 0,
        scanCode: 0,
        gesture: HardwareVoiceGesture.single,
      ),
    );
  }

  void _abortSessions() {
    final learn = _learnCompleter;
    if (learn != null && !learn.isCompleted) {
      learn.complete(
        const HardwareVoiceLearnResult(
          status: HardwareVoiceLearnStatus.cancelled,
        ),
      );
    }
    _learnCompleter = null;
    final test = _testCompleter;
    if (test != null && !test.isCompleted) {
      test.complete(
        const HardwareVoiceTestResult(
          status: HardwareVoiceTestStatus.cancelled,
        ),
      );
    }
    _testCompleter = null;
    _learnHint = null;
    _phase = HardwareVoiceUiPhase.idle;
  }

  void _onNativeVoiceTrigger() {
    if (_phase != HardwareVoiceUiPhase.idle) {
      return;
    }
    if (!hasEnabledBinding) {
      return;
    }
    final handler = onShellVoiceTrigger;
    if (handler == null) {
      return;
    }
    unawaited(handler());
  }

  void _onNativeLearnResult(HardwareVoiceLearnResult result) {
    if (_phase != HardwareVoiceUiPhase.learning) {
      return;
    }
    if (result.status == HardwareVoiceLearnStatus.rejected) {
      _learnHint =
          result.message ?? 'Эту кнопку нельзя назначить голосовому помощнику.';
      notifyListeners();
      return;
    }
    _phase = HardwareVoiceUiPhase.idle;
    _learnHint = null;
    final completer = _learnCompleter;
    _learnCompleter = null;
    if (completer != null && !completer.isCompleted) {
      completer.complete(result);
    }
    notifyListeners();
    unawaited(_restoreNativeAfterSession());
  }

  void _onNativeTestResult(HardwareVoiceTestResult result) {
    if (_phase != HardwareVoiceUiPhase.testing) {
      return;
    }
    _phase = HardwareVoiceUiPhase.idle;
    final completer = _testCompleter;
    _testCompleter = null;
    if (completer != null && !completer.isCompleted) {
      completer.complete(result);
    }
    notifyListeners();
    unawaited(_restoreNativeAfterSession());
  }

  Future<void> _restoreNativeAfterSession() async {
    final current = _binding;
    if (current != null && current.enabled) {
      await _configureNative(current);
    } else {
      await _disableNative();
    }
  }

  @override
  void dispose() {
    _authController.removeListener(_onAuthChanged);
    onShellVoiceTrigger = null;
    _abortSessions();
    _bridge.dispose();
    super.dispose();
  }
}
