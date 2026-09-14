import 'package:personal_secretary/assistant/hardware_voice_bridge.dart';
import 'package:personal_secretary/assistant/hardware_voice_keys.dart';

class FakeHardwareVoiceBridge implements HardwareVoiceBridge {
  HardwareVoiceBridgeListener? listener;
  HardwareVoiceNativeConfig? lastConfig;
  int configureCount = 0;
  int startLearnCount = 0;
  int cancelLearnCount = 0;
  int startTestCount = 0;
  int cancelTestCount = 0;
  bool disposed = false;

  bool get nativeEnabled => lastConfig?.enabled == true;

  @override
  void setListener(HardwareVoiceBridgeListener? next) {
    listener = next;
  }

  @override
  Future<void> configure(HardwareVoiceNativeConfig config) async {
    configureCount += 1;
    lastConfig = config;
  }

  @override
  Future<void> startLearn({int timeoutMs = hardwareVoiceLearnTimeoutMs}) async {
    startLearnCount += 1;
  }

  @override
  Future<void> cancelLearn() async {
    cancelLearnCount += 1;
    listener?.onLearnResult(
      const HardwareVoiceLearnResult(
        status: HardwareVoiceLearnStatus.cancelled,
      ),
    );
  }

  @override
  Future<void> startTest({int timeoutMs = hardwareVoiceLearnTimeoutMs}) async {
    startTestCount += 1;
  }

  @override
  Future<void> cancelTest() async {
    cancelTestCount += 1;
    listener?.onTestResult(
      const HardwareVoiceTestResult(status: HardwareVoiceTestStatus.cancelled),
    );
  }

  @override
  void dispose() {
    disposed = true;
    listener = null;
  }
}
