import 'package:flutter/material.dart';

import '../account/account_screen.dart';
import '../api/api_models.dart';
import '../assistant/assistant_controller.dart';
import '../assistant/assistant_screen.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../inbox/inbox_screen.dart';
import '../navigation/secretary_navigation.dart';
import '../graph/graph_workspace_controller.dart';
import '../graph/graph_workspace_screen.dart';
import '../search/search_screen.dart';
import '../today/temporal_area.dart';
import '../ui/object_bookmark_controller.dart';
import '../ui/shell_clock.dart';

const double kShellWideBreakpoint = 600;

enum ShellDestination {
  inbox('Входящие'),
  today('Сегодня'),
  graph('Граф'),
  search('Поиск'),
  assistant('Секретарь');

  const ShellDestination(this.label);
  final String label;
}

class AppShell extends StatefulWidget {
  const AppShell({
    super.key,
    required this.authController,
    required this.captureController,
    required this.assistantController,
    required this.graphController,
    this.bookmarkController,
  });

  final AuthController authController;
  final CaptureController captureController;
  final AssistantController assistantController;
  final GraphWorkspaceController graphController;
  final ObjectBookmarkController? bookmarkController;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _selectedIndex = 0;
  late final ObjectBookmarkController _bookmarks;
  var _ownsBookmarks = false;

  @override
  void initState() {
    super.initState();
    final provided = widget.bookmarkController;
    if (provided != null) {
      _bookmarks = provided;
    } else {
      _ownsBookmarks = true;
      _bookmarks = ObjectBookmarkController(
        apiClient: widget.authController.apiClient,
        authController: widget.authController,
      );
    }
  }

  @override
  void dispose() {
    if (_ownsBookmarks) {
      _bookmarks.dispose();
    }
    super.dispose();
  }

  void _openCapture() {
    openCapture(
      context,
      captureController: widget.captureController,
      authController: widget.authController,
    );
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

  void _selectDestination(int index) {
    final previous = ShellDestination.values[_selectedIndex];
    final next = ShellDestination.values[index];
    setState(() => _selectedIndex = index);
    if (next == ShellDestination.graph && previous != ShellDestination.graph) {
      widget.graphController.refreshCurrentWorkspace();
    }
  }

  void _showInGraph(String objectId) {
    widget.graphController.reRoot(objectId);
    if (_selectedIndex != ShellDestination.graph.index) {
      setState(() => _selectedIndex = ShellDestination.graph.index);
    }
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
          bookmarkController: _bookmarks,
          onAskSecretary: _askSecretaryAbout,
          onAskSecretaryAboutNotification: _askSecretaryAboutNotification,
          onShowInGraph: _showInGraph,
        );
      case ShellDestination.today:
        return TemporalArea(
          apiClient: widget.authController.apiClient,
          authController: widget.authController,
          captureController: widget.captureController,
          assistantController: widget.assistantController,
          bookmarkController: _bookmarks,
          onAskSecretary: _askSecretaryAbout,
          onShowInGraph: _showInGraph,
        );
      case ShellDestination.search:
        return SearchScreen(
          apiClient: widget.authController.apiClient,
          authController: widget.authController,
          captureController: widget.captureController,
          assistantController: widget.assistantController,
          bookmarkController: _bookmarks,
          onAskSecretary: _askSecretaryAbout,
          onShowInGraph: _showInGraph,
        );
      case ShellDestination.assistant:
        return AssistantScreen(
          controller: widget.assistantController,
          apiClient: widget.authController.apiClient,
          authController: widget.authController,
          captureController: widget.captureController,
          bookmarkController: _bookmarks,
        );
      case ShellDestination.graph:
        return GraphWorkspaceScreen(
          controller: widget.graphController,
          apiClient: widget.authController.apiClient,
          authController: widget.authController,
          captureController: widget.captureController,
          assistantController: widget.assistantController,
          bookmarkController: _bookmarks,
          onAskSecretary: _askSecretaryAbout,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final destination = ShellDestination.values[_selectedIndex];
    final isWide = MediaQuery.sizeOf(context).width >= kShellWideBreakpoint;
    final showRailClock = isWide && MediaQuery.sizeOf(context).height >= 520;

    final captureAction = isWide
        ? Padding(
            padding: const EdgeInsets.fromLTRB(8, 8, 8, 4),
            child: FilledButton.icon(
              key: const Key('shell_add_button'),
              onPressed: _openCapture,
              icon: const Icon(Icons.add),
              label: const Text('Задача'),
            ),
          )
        : null;

    final accountAction = IconButton(
      key: const Key('shell_account_button'),
      icon: const Icon(Icons.account_circle),
      tooltip: 'Аккаунт',
      onPressed: _openAccount,
    );

    if (isWide) {
      return Scaffold(
        body: Row(
          children: [
            NavigationRail(
              selectedIndex: _selectedIndex,
              onDestinationSelected: _selectDestination,
              labelType: NavigationRailLabelType.all,
              groupAlignment: -1.0,
              leadingAtTop: true,
              trailingAtBottom: true,
              leading: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  captureAction!,
                  if (showRailClock) const ShellClock(key: Key('shell_clock')),
                ],
              ),
              trailing: accountAction,
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
        actions: [
          if (!isWide &&
              (destination == ShellDestination.assistant ||
                  destination == ShellDestination.graph))
            IconButton(
              icon: const Icon(Icons.add),
              tooltip: 'Задача',
              onPressed: _openCapture,
            ),
          accountAction,
        ],
      ),
      body: _destinationScreen(destination),
      floatingActionButton:
          isWide ||
              destination == ShellDestination.assistant ||
              destination == ShellDestination.graph
          ? null
          : FloatingActionButton.extended(
              onPressed: _openCapture,
              icon: const Icon(Icons.add),
              label: const Text('Задача'),
            ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: _selectDestination,
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
