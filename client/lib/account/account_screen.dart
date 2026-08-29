import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';

class AccountScreen extends StatefulWidget {
  const AccountScreen({
    super.key,
    required this.apiClient,
    required this.authController,
  });

  final SecretaryApiClient apiClient;
  final AuthController authController;

  @override
  State<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen> {
  Connections? _connections;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadConnections();
  }

  Future<void> _loadConnections() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final connections = await widget.apiClient.getConnections();
      if (mounted) {
        setState(() {
          _connections = connections;
          _loading = false;
        });
      }
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (mounted) {
        setState(() {
          _error = e.message;
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = widget.authController.user;

    return Scaffold(
      appBar: AppBar(title: const Text('Account')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Display name', style: Theme.of(context).textTheme.titleSmall),
          Text(user?.displayName ?? '—'),
          const SizedBox(height: 16),
          Text('Connections', style: Theme.of(context).textTheme.titleSmall),
          if (_loading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (_error != null)
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error))
          else if (_connections != null)
            _ConnectionsList(connections: _connections!),
          const SizedBox(height: 24),
          OutlinedButton(
            onPressed: () async {
              final navigator = Navigator.of(context);
              await widget.authController.forgetToken();
              navigator.pop();
            },
            child: const Text('Forget token / disconnect this client'),
          ),
        ],
      ),
    );
  }
}

class _ConnectionsList extends StatelessWidget {
  const _ConnectionsList({required this.connections});

  final Connections connections;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _ConnectionRow(
          label: 'Google',
          connected: connections.google.connected,
          detail: connections.google.email,
        ),
        _ConnectionRow(
          label: 'Gmail available',
          connected: connections.google.gmailAvailable,
        ),
        _ConnectionRow(
          label: 'Google Calendar available',
          connected: connections.google.calendarAvailable,
        ),
        _ConnectionRow(
          label: 'Yandex Mail',
          connected: connections.yandexMail.connected,
          detail: connections.yandexMail.email,
        ),
        _ConnectionRow(
          label: 'Yandex Calendar',
          connected: connections.yandexCalendar.connected,
          detail: connections.yandexCalendar.email,
        ),
      ],
    );
  }
}

class _ConnectionRow extends StatelessWidget {
  const _ConnectionRow({
    required this.label,
    required this.connected,
    this.detail,
  });

  final String label;
  final bool connected;
  final String? detail;

  @override
  Widget build(BuildContext context) {
    final status = connected ? 'connected' : 'disconnected';
    final suffix = detail != null && detail!.isNotEmpty ? ' ($detail)' : '';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Text('$label: $status$suffix'),
    );
  }
}
