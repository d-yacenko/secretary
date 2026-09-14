import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/account/account_screen.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/assistant/system_assistant_bridge.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/auth/token_store.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'account_test_helpers.dart';

class FakeSystemAssistantBridge implements SystemAssistantBridge {
  FakeSystemAssistantBridge({
    this.isDefaultAssistant = false,
    this.keyguardLocked = false,
  });

  bool isDefaultAssistant;
  bool keyguardLocked;
  int requestCount = 0;
  VoidCallback? onAssist;
  void Function(bool locked)? onKeyguard;

  @override
  void setOnAssist(VoidCallback? callback) {
    onAssist = callback;
  }

  @override
  void setOnKeyguard(void Function(bool locked)? callback) {
    onKeyguard = callback;
  }

  @override
  Future<SystemAssistantStatus> getStatus() async {
    return SystemAssistantStatus(
      available: true,
      isDefaultAssistant: isDefaultAssistant,
      roleManagerAvailable: true,
      keyguardLocked: keyguardLocked,
      protocol: systemAssistantProtocol,
    );
  }

  @override
  Future<void> requestAssistantRole() async {
    requestCount += 1;
    isDefaultAssistant = true;
  }

  @override
  Future<void> dismiss() async {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('Android account shows system assistant opt-in', (tester) async {
    final client = buildAccountApiClient();
    final auth = AuthController(
      apiClient: client,
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    auth.user = UserMe(
      id: 'user-1',
      displayName: 'Alice',
      createdAt: '2026-01-01T00:00:00Z',
    );
    final bridge = FakeSystemAssistantBridge();
    final controller = SystemAssistantController(
      bridge: bridge,
      store: LockScreenVoiceStore(
        preferences: await SharedPreferences.getInstance(),
      ),
    );
    await controller.attach('user-1');
    await pumpAccountReady(
      tester,
      AccountScreen(
        apiClient: client,
        authController: auth,
        initialConnections: Connections.fromJson(accountConnectionsJson()),
        initialSettings: UserSettings.fromJson(accountSettingsJson()),
        initialSourcePreferences: SourcePreferenceList.fromJson(
          accountSourcePreferencesJson(),
        ).preferences,
        initialIdentity: UserIdentity.fromJson(accountIdentityJson()),
        initialSemanticContext: UserSemanticContext.fromJson(
          accountSemanticContextJson(),
        ),
        systemAssistantController: controller,
        systemAssistantPlatform: TargetPlatform.android,
      ),
    );
    expect(find.text('Системный помощник'), findsOneWidget);
    expect(
      find.text('Секретарь не выбран системным помощником'),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('system_assistant_lock_screen')),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('system_assistant_request_role')));
    await tester.pump();
    expect(bridge.requestCount, 1);
    controller.dispose();
  });

  test('lock-screen voice pref is per user and defaults off', () async {
    final prefs = await SharedPreferences.getInstance();
    final store = LockScreenVoiceStore(preferences: prefs);
    expect(await store.load('user-a'), isFalse);
    await store.save('user-a', true);
    expect(await store.load('user-a'), isTrue);
    expect(await store.load('user-b'), isFalse);
  });
}
