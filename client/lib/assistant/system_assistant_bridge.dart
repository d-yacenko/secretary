import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

const String systemAssistantChannelName = 'secretary/system_assistant';
const String systemAssistantProtocol = 'secretary.system_assistant.v1';

const String lockScreenVoiceEnabledMessage =
    'Голос с заблокированного экрана выключен.';
const String lockScreenSignInMessage =
    'Сначала войдите в Секретарь на этом устройстве.';

class SystemAssistantStatus {
  const SystemAssistantStatus({
    required this.available,
    required this.isDefaultAssistant,
    required this.roleManagerAvailable,
    required this.keyguardLocked,
    this.protocol = '',
  });

  final bool available;
  final bool isDefaultAssistant;
  final bool roleManagerAvailable;
  final bool keyguardLocked;
  final String protocol;

  bool get isHealthy => available && protocol == systemAssistantProtocol;
}

abstract class SystemAssistantBridge {
  void setOnAssist(VoidCallback? callback);

  void setOnKeyguard(void Function(bool locked)? callback);

  Future<SystemAssistantStatus> getStatus();

  Future<void> requestAssistantRole();

  Future<void> dismiss();
}

class NoopSystemAssistantBridge implements SystemAssistantBridge {
  @override
  void setOnAssist(VoidCallback? callback) {}

  @override
  void setOnKeyguard(void Function(bool locked)? callback) {}

  @override
  Future<SystemAssistantStatus> getStatus() async {
    return const SystemAssistantStatus(
      available: false,
      isDefaultAssistant: false,
      roleManagerAvailable: false,
      keyguardLocked: false,
    );
  }

  @override
  Future<void> requestAssistantRole() async {}

  @override
  Future<void> dismiss() async {}
}

class MethodChannelSystemAssistantBridge implements SystemAssistantBridge {
  MethodChannelSystemAssistantBridge({MethodChannel? channel})
    : _channel = channel ?? const MethodChannel(systemAssistantChannelName) {
    _channel.setMethodCallHandler(_onCall);
  }

  final MethodChannel _channel;
  VoidCallback? _onAssist;
  void Function(bool locked)? _onKeyguard;

  @override
  void setOnAssist(VoidCallback? callback) {
    _onAssist = callback;
  }

  @override
  void setOnKeyguard(void Function(bool locked)? callback) {
    _onKeyguard = callback;
  }

  @override
  Future<SystemAssistantStatus> getStatus() async {
    try {
      final raw = await _channel.invokeMethod<dynamic>('getStatus');
      return _parse(raw);
    } on MissingPluginException {
      return const SystemAssistantStatus(
        available: false,
        isDefaultAssistant: false,
        roleManagerAvailable: false,
        keyguardLocked: false,
      );
    } on PlatformException {
      return const SystemAssistantStatus(
        available: false,
        isDefaultAssistant: false,
        roleManagerAvailable: false,
        keyguardLocked: false,
      );
    }
  }

  @override
  Future<void> requestAssistantRole() async {
    try {
      await _channel.invokeMethod<void>('requestAssistantRole');
    } on MissingPluginException {
      return;
    } on PlatformException {
      return;
    }
  }

  @override
  Future<void> dismiss() async {
    try {
      await _channel.invokeMethod<void>('dismiss');
    } on MissingPluginException {
      return;
    } on PlatformException {
      return;
    }
  }

  Future<dynamic> _onCall(MethodCall call) async {
    switch (call.method) {
      case 'onAssistInvoke':
        _onAssist?.call();
        return null;
      case 'onKeyguard':
        final locked = call.arguments == true;
        _onKeyguard?.call(locked);
        return null;
      default:
        return null;
    }
  }

  SystemAssistantStatus _parse(dynamic arguments) {
    if (arguments is! Map) {
      return const SystemAssistantStatus(
        available: false,
        isDefaultAssistant: false,
        roleManagerAvailable: false,
        keyguardLocked: false,
      );
    }
    final map = Map<Object?, Object?>.from(arguments);
    return SystemAssistantStatus(
      available: map['available'] == true,
      isDefaultAssistant: map['isDefaultAssistant'] == true,
      roleManagerAvailable: map['roleManagerAvailable'] == true,
      keyguardLocked: map['keyguardLocked'] == true,
      protocol: map['protocol'] as String? ?? '',
    );
  }
}

class LockScreenVoiceStore {
  LockScreenVoiceStore({SharedPreferences? preferences})
    : _preferencesFuture = preferences != null
          ? Future.value(preferences)
          : SharedPreferences.getInstance();

  final Future<SharedPreferences> _preferencesFuture;

  static String prefKeyForUser(String userId) =>
      'lock_screen_voice_enabled.$userId';

  Future<bool> load(String userId) async {
    if (userId.isEmpty) {
      return false;
    }
    final prefs = await _preferencesFuture;
    return prefs.getBool(prefKeyForUser(userId)) ?? false;
  }

  Future<void> save(String userId, bool enabled) async {
    if (userId.isEmpty) {
      return;
    }
    final prefs = await _preferencesFuture;
    await prefs.setBool(prefKeyForUser(userId), enabled);
  }
}

class SystemAssistantController extends ChangeNotifier {
  SystemAssistantController({
    SystemAssistantBridge? bridge,
    LockScreenVoiceStore? store,
  }) : _bridge =
           bridge ??
           (!kIsWeb && Platform.isAndroid
               ? MethodChannelSystemAssistantBridge()
               : NoopSystemAssistantBridge()),
       _store = store ?? LockScreenVoiceStore() {
    _bridge.setOnAssist(() {
      onAssistInvoke?.call();
    });
    _bridge.setOnKeyguard((locked) {
      keyguardLocked = locked;
      notifyListeners();
    });
  }

  final SystemAssistantBridge _bridge;
  final LockScreenVoiceStore _store;

  VoidCallback? onAssistInvoke;

  bool available = false;
  bool isDefaultAssistant = false;
  bool roleManagerAvailable = false;
  bool keyguardLocked = false;
  bool lockScreenVoiceEnabled = false;
  String? _userId;

  Future<void> attach(String? userId) async {
    _userId = userId;
    if (userId != null && userId.isNotEmpty) {
      lockScreenVoiceEnabled = await _store.load(userId);
    } else {
      lockScreenVoiceEnabled = false;
    }
    await refresh();
  }

  Future<void> refresh() async {
    final status = await _bridge.getStatus();
    available = status.isHealthy;
    isDefaultAssistant = status.isDefaultAssistant;
    roleManagerAvailable = status.roleManagerAvailable;
    keyguardLocked = status.keyguardLocked;
    notifyListeners();
  }

  Future<void> requestAssistantRole() async {
    await _bridge.requestAssistantRole();
    await refresh();
  }

  Future<void> setLockScreenVoiceEnabled(bool enabled) async {
    lockScreenVoiceEnabled = enabled;
    final userId = _userId;
    if (userId != null) {
      await _store.save(userId, enabled);
    }
    notifyListeners();
  }

  Future<void> dismissOverlay() => _bridge.dismiss();

  @override
  void dispose() {
    _bridge.setOnAssist(null);
    _bridge.setOnKeyguard(null);
    super.dispose();
  }
}

bool systemAssistantSettingsVisible({TargetPlatform? platform}) {
  final resolved = platform ?? defaultTargetPlatform;
  return !kIsWeb && resolved == TargetPlatform.android;
}
