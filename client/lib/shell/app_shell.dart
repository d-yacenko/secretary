import 'package:flutter/material.dart';

import '../account/account_screen.dart';
import '../api/api_models.dart';
import '../assistant/assistant_controller.dart';
import '../assistant/assistant_screen.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../inbox/inbox_screen.dart';
import '../navigation/secretary_navigation.dart';
import '../screens/placeholder_screen.dart';
import '../search/search_screen.dart';
import '../today/today_screen.dart';

const double kShellWideBreakpoint = 600;

enum ShellDestination {
  inbox('Inbox'),
  today('Today'),
  graph('Graph'),
  search('Search'),
  assistant('Assistant');

  const ShellDestination(this.label);
  final String label;
}

class AppShell extends StatefulWidget {
  const AppShell({
    super.key,
    required this.authController,
    required this.captureController,
    required this.assistantController,
  });

  final AuthController authController;
  final CaptureController captureController;
  final AssistantController assistantController;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _selectedIndex = 0;

  void _openCapture() {
    openCapture(context, captureController: widget.captureController);
  }

  void _openAccount() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) => AccountScreen(
          apiClient: widget.authController.apiClient,
          authController: widget.authController,
        ),
      ),
    );
  }

  void _askSecretaryAbout(SecretaryObject object) {
    widget.assistantController.setObjectContext(object);
    setState(() => _selectedIndex = ShellDestination.assistant.index);
  }

  void _askSecretaryAboutNotification(NotificationOut notification) {
    widget.assistantController.setNotificationContext(notification);
    setState(() => _selectedIndex = ShellDestination.assistant.index);
  }

  Widget _destinationScreen(ShellDestination destination) {
    switch (destination) {
      case ShellDestination.inbox:
        return InboxScreen(
          apiClient: widget.authController.apiClient,
          authController: widget.authController,
          captureController: widget.captureController,
          assistantController: widget.assistantController,
          onAskSecretary: _askSecretaryAbout,
          onAskSecretaryAboutNotification: _askSecretaryAboutNotification,
        );
      case ShellDestination.today:
        return TodayScreen(
          apiClient: widget.authController.apiClient,
          authController: widget.authController,
          captureController: widget.captureController,
          assistantController: widget.assistantController,
          onAskSecretary: _askSecretaryAbout,
        );
      case ShellDestination.search:
        return SearchScreen(
          apiClient: widget.authController.apiClient,
          authController: widget.authController,
          captureController: widget.captureController,
          assistantController: widget.assistantController,
          onAskSecretary: _askSecretaryAbout,
        );
      case ShellDestination.assistant:
        return AssistantScreen(
          controller: widget.assistantController,
          apiClient: widget.authController.apiClient,
          authController: widget.authController,
          captureController: widget.captureController,
        );
      case ShellDestination.graph:
        return PlaceholderScreen(title: destination.label);
    }
  }

  @override
  Widget build(BuildContext context) {
    final destination = ShellDestination.values[_selectedIndex];
    final isWide = MediaQuery.sizeOf(context).width >= kShellWideBreakpoint;

    final captureAction = isWide
        ? Padding(
            padding: const EdgeInsets.all(8),
            child: FilledButton.icon(
              onPressed: _openCapture,
              icon: const Icon(Icons.add),
              label: const Text('Capture'),
            ),
          )
        : null;

    final accountAction = IconButton(
      icon: const Icon(Icons.account_circle),
      tooltip: 'Account',
      onPressed: _openAccount,
    );

    if (isWide) {
      return Scaffold(
        body: Row(
          children: [
            NavigationRail(
              selectedIndex: _selectedIndex,
              onDestinationSelected: (index) => setState(() => _selectedIndex = index),
              labelType: NavigationRailLabelType.all,
              leading: captureAction,
              trailing: Expanded(
                child: Align(
                  alignment: Alignment.bottomCenter,
                  child: accountAction,
                ),
              ),
              destinations: ShellDestination.values
                  .map(
                    (d) => NavigationRailDestination(
                      icon: Icon(_iconFor(d)),
                      label: Text(d.label),
                    ),
                  )
                  .toList(),
            ),
            const VerticalDivider(width: 1),
            Expanded(child: _destinationScreen(destination)),
          ],
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(destination.label),
        actions: [accountAction],
      ),
      body: _destinationScreen(destination),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openCapture,
        icon: const Icon(Icons.add),
        label: const Text('Capture'),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) => setState(() => _selectedIndex = index),
        destinations: ShellDestination.values
            .map(
              (d) => NavigationDestination(
                icon: Icon(_iconFor(d)),
                label: d.label,
              ),
            )
            .toList(),
      ),
    );
  }

  IconData _iconFor(ShellDestination destination) {
    switch (destination) {
      case ShellDestination.inbox:
        return Icons.inbox_outlined;
      case ShellDestination.today:
        return Icons.today_outlined;
      case ShellDestination.graph:
        return Icons.hub_outlined;
      case ShellDestination.search:
        return Icons.search;
      case ShellDestination.assistant:
        return Icons.smart_toy_outlined;
    }
  }
}
