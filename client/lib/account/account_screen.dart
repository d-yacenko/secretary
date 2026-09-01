import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart' as url_launcher;

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';
import '../local/local_intake_actions.dart';
import '../ui/domain_labels.dart';

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

class _AccountScreenState extends State<AccountScreen> with WidgetsBindingObserver {
  Connections? _connections;
  String? _error;
  bool _loading = true;
  bool _googleOAuthPending = false;
  late final LocalIntakeActions _intakeActions;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _intakeActions = LocalIntakeActions(
      apiClient: widget.apiClient,
      authController: widget.authController,
    );
    _loadConnections();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _loadConnections();
    }
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

  Future<void> _startGoogleOAuth() async {
    if (_googleOAuthPending) {
      return;
    }
    setState(() => _googleOAuthPending = true);
    try {
      final result = await widget.apiClient.getGoogleAuthorizationUrl();
      final uri = Uri.tryParse(result.authorizationUrl);
      if (uri == null) {
        throw ServerException('Не удалось открыть страницу авторизации Google');
      }
      final launched = await url_launcher.launchUrl(
        uri,
        mode: url_launcher.LaunchMode.externalApplication,
      );
      if (!launched && mounted) {
        setState(() => _error = 'Не удалось открыть браузер для авторизации Google');
      }
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (mounted) {
        setState(() => _error = e.message);
      }
    } finally {
      if (mounted) {
        setState(() => _googleOAuthPending = false);
      }
    }
  }

  Future<void> _showConnectMattermostDialog() async {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => _MattermostConnectDialog(
        apiClient: widget.apiClient,
        authController: widget.authController,
        onConnected: _loadConnections,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = widget.authController.user;

    return Scaffold(
      appBar: AppBar(title: const Text('Аккаунт')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Отображаемое имя', style: Theme.of(context).textTheme.titleSmall),
          Text(user?.displayName ?? '—'),
          const SizedBox(height: 16),
          Text('Подключения', style: Theme.of(context).textTheme.titleSmall),
          if (_loading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (_error != null)
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error))
          else if (_connections != null)
            _ConnectionsList(
              connections: _connections!,
              googleOAuthPending: _googleOAuthPending,
              onConnectGoogle: _startGoogleOAuth,
              onConnectMattermost: _showConnectMattermostDialog,
            ),
          const SizedBox(height: 16),
          Text('Локальные файлы', style: Theme.of(context).textTheme.titleSmall),
          buildAddFileButton(actions: _intakeActions, context: context),
          buildAddFolderButton(actions: _intakeActions, context: context),
          const SizedBox(height: 24),
          OutlinedButton(
            onPressed: () async {
              final navigator = Navigator.of(context);
              await widget.authController.forgetToken();
              navigator.pop();
            },
            child: const Text('Забыть токен / отключить клиент'),
          ),
        ],
      ),
    );
  }
}

String googleOAuthButtonLabel(GoogleConnection google) {
  if (!google.connected) {
    return 'Подключить Google';
  }
  if (!google.driveAvailable) {
    return 'Разрешить Google Drive';
  }
  return 'Переподключить Google';
}

class _ConnectionsList extends StatelessWidget {
  const _ConnectionsList({
    required this.connections,
    required this.googleOAuthPending,
    required this.onConnectGoogle,
    required this.onConnectMattermost,
  });

  final Connections connections;
  final bool googleOAuthPending;
  final VoidCallback onConnectGoogle;
  final VoidCallback onConnectMattermost;

  @override
  Widget build(BuildContext context) {
    final google = connections.google;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _ConnectionRow(
          label: 'Google',
          connected: google.connected,
          detail: google.email,
        ),
        _ConnectionRow(
          label: 'Gmail доступен',
          connected: google.gmailAvailable,
        ),
        _ConnectionRow(
          label: 'Google Календарь доступен',
          connected: google.calendarAvailable,
        ),
        _ConnectionRow(
          label: 'Google Drive доступен',
          connected: google.driveAvailable,
        ),
        const SizedBox(height: 8),
        OutlinedButton(
          onPressed: googleOAuthPending ? null : onConnectGoogle,
          child: Text(googleOAuthButtonLabel(google)),
        ),
        _ConnectionRow(
          label: 'Яндекс Почта',
          connected: connections.yandexMail.connected,
          detail: connections.yandexMail.email,
        ),
        _ConnectionRow(
          label: 'Яндекс Календарь',
          connected: connections.yandexCalendar.connected,
          detail: connections.yandexCalendar.email,
        ),
        for (final account in connections.mattermost)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Text(mattermostConnectionLabel(account)),
          ),
        const SizedBox(height: 8),
        OutlinedButton(
          onPressed: onConnectMattermost,
          child: const Text('Подключить Mattermost'),
        ),
      ],
    );
  }
}

String mattermostConnectionLabel(MattermostConnection account) {
  final displayName = account.displayName?.trim();
  final name = displayName != null && displayName.isNotEmpty
      ? displayName
      : account.username;
  final host = account.serverUrl.replaceFirst(RegExp(r'^https?://'), '');
  return 'Mattermost: $name @ $host';
}

class _MattermostConnectDialog extends StatefulWidget {
  const _MattermostConnectDialog({
    required this.apiClient,
    required this.authController,
    required this.onConnected,
  });

  final SecretaryApiClient apiClient;
  final AuthController authController;
  final Future<void> Function() onConnected;

  @override
  State<_MattermostConnectDialog> createState() => _MattermostConnectDialogState();
}

class _MattermostConnectDialogState extends State<_MattermostConnectDialog> {
  final _serverController = TextEditingController();
  final _patController = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _serverController.dispose();
    _patController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_submitting) {
      return;
    }
    final serverUrl = _serverController.text.trim();
    final accessToken = _patController.text.trim();
    if (serverUrl.isEmpty || accessToken.isEmpty) {
      setState(() {
        _error = 'Укажите URL сервера и Personal Access Token';
      });
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      await widget.apiClient.connectMattermost(
        serverUrl: serverUrl,
        accessToken: accessToken,
      );
      _patController.clear();
      await widget.onConnected();
      if (mounted) {
        Navigator.of(context).pop();
      }
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
      if (mounted) {
        Navigator.of(context).pop();
      }
    } on ApiException catch (e) {
      _patController.clear();
      if (mounted) {
        setState(() {
          _error = e.message;
          _submitting = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Подключить Mattermost'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _serverController,
              decoration: const InputDecoration(
                labelText: 'Server URL',
                hintText: 'https://mattermost.example.com',
              ),
              enabled: !_submitting,
              keyboardType: TextInputType.url,
              textInputAction: TextInputAction.next,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _patController,
              decoration: const InputDecoration(
                labelText: 'Personal Access Token',
              ),
              enabled: !_submitting,
              obscureText: true,
              autocorrect: false,
              enableSuggestions: false,
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _submit(),
            ),
            if (_submitting) ...[
              const SizedBox(height: 16),
              const Center(
                child: SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _submitting ? null : () => Navigator.of(context).pop(),
          child: const Text('Отмена'),
        ),
        FilledButton(
          onPressed: _submitting ? null : _submit,
          child: const Text('Подключить'),
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
    final status = connectionStatusLabel(connected);
    final suffix = detail != null && detail!.isNotEmpty ? ' ($detail)' : '';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Text('$label: $status$suffix'),
    );
  }
}
