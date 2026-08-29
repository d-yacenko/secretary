import 'package:flutter/material.dart';

import '../account/account_screen.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../inbox/inbox_screen.dart';
import '../navigation/secretary_navigation.dart';
import '../screens/placeholder_screen.dart';
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
  });

  final AuthController authController;
  final CaptureController captureController;

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

  Widget _destinationScreen(ShellDestination destination) {
    switch (destination) {
      case ShellDestination.inbox:
        return InboxScreen(
          apiClient: widget.authController.apiClient,
          authController: widget.authController,
          captureController: widget.captureController,
        );
      case ShellDestination.today:
        return TodayScreen(
          apiClient: widget.authController.apiClient,
          authController: widget.authController,
          captureController: widget.captureController,
        );
      case ShellDestination.graph:
      case ShellDestination.search:
      case ShellDestination.assistant:
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
