import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/api/secretary_api_client.dart';
import 'package:personal_secretary/auth/auth_controller.dart';
import 'package:personal_secretary/auth/server_url_store.dart';
import 'package:personal_secretary/auth/token_store.dart';
import 'package:personal_secretary/capture/capture_controller.dart';
import 'package:personal_secretary/shell/app_shell.dart';

void main() {
  testWidgets('narrow layout exposes five destinations and Capture FAB', (tester) async {
    tester.view.physicalSize = const Size(400, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final auth = AuthController(
      apiClient: SecretaryApiClient(),
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    auth.user = UserMe(
      id: 'u1',
      displayName: 'Alice',
      createdAt: '2026-01-01T00:00:00Z',
    );

    final capture = CaptureController(
      apiClient: auth.apiClient,
      authController: auth,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: AppShell(authController: auth, captureController: capture),
      ),
    );

    for (final label in ['Inbox', 'Today', 'Graph', 'Search', 'Assistant']) {
      expect(find.text(label), findsWidgets);
    }
    expect(find.text('Capture'), findsOneWidget);
    expect(find.byType(NavigationBar), findsOneWidget);
  });

  testWidgets('wide layout exposes NavigationRail and prominent Capture action', (tester) async {
    tester.view.physicalSize = const Size(900, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final auth = AuthController(
      apiClient: SecretaryApiClient(),
      tokenStore: FakeTokenStore(),
      serverUrlStore: FakeServerUrlStore(),
    );
    auth.status = AuthStatus.authenticated;
    auth.user = UserMe(
      id: 'u1',
      displayName: 'Alice',
      createdAt: '2026-01-01T00:00:00Z',
    );

    final capture = CaptureController(
      apiClient: auth.apiClient,
      authController: auth,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: AppShell(authController: auth, captureController: capture),
      ),
    );

    expect(find.byType(NavigationRail), findsOneWidget);
    expect(find.text('Capture'), findsOneWidget);
    expect(find.byType(FloatingActionButton), findsNothing);
  });
}
