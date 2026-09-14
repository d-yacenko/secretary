import 'package:flutter/services.dart';

import 'hardware_voice_binding.dart';
import 'hardware_voice_keys.dart';

const hardwareVoiceChannelName = 'secretary/hardware_voice';

class HardwareVoiceNativeConfig {
  const HardwareVoiceNativeConfig({
    required this.enabled,
    required this.keyCode,
    required this.scanCode,
    required this.gesture,
  });

  final bool enabled;
  final int keyCode;
  final int scanCode;
  final HardwareVoiceGesture gesture;

  Map<String, dynamic> toMap() {
    return {
      'enabled': enabled,
      'keyCode': keyCode,
      'scanCode': scanCode,
      'gesture': gesture == HardwareVoiceGesture.doublePress
          ? 'double'
          : 'single',
    };
  }
}

enum HardwareVoiceLearnStatus { captured, rejected, timeout, cancelled }

class HardwareVoiceLearnResult {
  const HardwareVoiceLearnResult({
    required this.status,
    this.keyCode,
    this.scanCode = 0,
    this.androidKeyName,
    this.message,
  });

  final HardwareVoiceLearnStatus status;
  final int? keyCode;
  final int scanCode;
  final String? androidKeyName;
  final String? message;

  bool get isCaptured =>
      status == HardwareVoiceLearnStatus.captured && keyCode != null;
}

enum HardwareVoiceTestStatus { recognized, timeout, cancelled }

class HardwareVoiceTestResult {
  const HardwareVoiceTestResult({required this.status});

  final HardwareVoiceTestStatus status;

  bool get isRecognized => status == HardwareVoiceTestStatus.recognized;
}

abstract class HardwareVoiceBridge {
  void setListener(HardwareVoiceBridgeListener? listener);

  Future<void> configure(HardwareVoiceNativeConfig config);

  Future<void> startLearn({int timeoutMs = hardwareVoiceLearnTimeoutMs});

  Future<void> cancelLearn();

  Future<void> startTest({int timeoutMs = hardwareVoiceLearnTimeoutMs});

  Future<void> cancelTest();

  void dispose();
}

class HardwareVoiceBridgeListener {
  const HardwareVoiceBridgeListener({
    required this.onVoiceTrigger,
    required this.onLearnResult,
    required this.onTestResult,
  });

  final void Function() onVoiceTrigger;
  final void Function(HardwareVoiceLearnResult result) onLearnResult;
  final void Function(HardwareVoiceTestResult result) onTestResult;
}

class NoopHardwareVoiceBridge implements HardwareVoiceBridge {
  @override
  void setListener(HardwareVoiceBridgeListener? listener) {}

  @override
  Future<void> configure(HardwareVoiceNativeConfig config) async {}

  @override
  Future<void> startLearn({
    int timeoutMs = hardwareVoiceLearnTimeoutMs,
  }) async {}

  @override
  Future<void> cancelLearn() async {}

  @override
  Future<void> startTest({int timeoutMs = hardwareVoiceLearnTimeoutMs}) async {}

  @override
  Future<void> cancelTest() async {}

  @override
  void dispose() {}
}

class MethodChannelHardwareVoiceBridge implements HardwareVoiceBridge {
  MethodChannelHardwareVoiceBridge({MethodChannel? channel})
    : _channel = channel ?? const MethodChannel(hardwareVoiceChannelName) {
    _channel.setMethodCallHandler(_onMethodCall);
  }

  final MethodChannel _channel;
  HardwareVoiceBridgeListener? _listener;

  @override
  void setListener(HardwareVoiceBridgeListener? listener) {
    _listener = listener;
  }

  @override
  Future<void> configure(HardwareVoiceNativeConfig config) async {
    await _channel.invokeMethod<void>('configure', config.toMap());
  }

  @override
  Future<void> startLearn({int timeoutMs = hardwareVoiceLearnTimeoutMs}) async {
    await _channel.invokeMethod<void>('startLearn', {'timeoutMs': timeoutMs});
  }

  @override
  Future<void> cancelLearn() async {
    await _channel.invokeMethod<void>('cancelLearn');
  }

  @override
  Future<void> startTest({int timeoutMs = hardwareVoiceLearnTimeoutMs}) async {
    await _channel.invokeMethod<void>('startTest', {'timeoutMs': timeoutMs});
  }

  @override
  Future<void> cancelTest() async {
    await _channel.invokeMethod<void>('cancelTest');
  }

  @override
  void dispose() {
    _listener = null;
    _channel.setMethodCallHandler(null);
  }

  Future<dynamic> _onMethodCall(MethodCall call) async {
    final listener = _listener;
    if (listener == null) {
      return null;
    }
    switch (call.method) {
      case 'onVoiceTrigger':
        listener.onVoiceTrigger();
        return null;
      case 'onLearnResult':
        listener.onLearnResult(_parseLearn(call.arguments));
        return null;
      case 'onTestResult':
        listener.onTestResult(_parseTest(call.arguments));
        return null;
      default:
        return null;
    }
  }

  HardwareVoiceLearnResult _parseLearn(dynamic arguments) {
    final map = arguments is Map
        ? Map<String, dynamic>.from(arguments)
        : <String, dynamic>{};
    final statusRaw = map['status'] as String? ?? 'timeout';
    final status = switch (statusRaw) {
      'captured' => HardwareVoiceLearnStatus.captured,
      'rejected' => HardwareVoiceLearnStatus.rejected,
      'cancelled' => HardwareVoiceLearnStatus.cancelled,
      _ => HardwareVoiceLearnStatus.timeout,
    };
    return HardwareVoiceLearnResult(
      status: status,
      keyCode: map['keyCode'] as int?,
      scanCode: map['scanCode'] as int? ?? 0,
      androidKeyName: map['androidKeyName'] as String?,
      message: map['message'] as String?,
    );
  }

  HardwareVoiceTestResult _parseTest(dynamic arguments) {
    final map = arguments is Map
        ? Map<String, dynamic>.from(arguments)
        : <String, dynamic>{};
    final statusRaw = map['status'] as String? ?? 'timeout';
    final status = switch (statusRaw) {
      'recognized' => HardwareVoiceTestStatus.recognized,
      'cancelled' => HardwareVoiceTestStatus.cancelled,
      _ => HardwareVoiceTestStatus.timeout,
    };
    return HardwareVoiceTestResult(status: status);
  }
}
