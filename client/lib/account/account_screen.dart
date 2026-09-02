import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart' as url_launcher;

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';
import '../ui/domain_labels.dart';

class AccountScreen extends StatefulWidget {
  const AccountScreen({
    super.key,
    required this.apiClient,
    required this.authController,
    this.initialConnections,
    this.initialSettings,
  });

  final SecretaryApiClient apiClient;
  final AuthController authController;
  final Connections? initialConnections;
  final UserSettings? initialSettings;

  @override
  State<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen> with WidgetsBindingObserver {
  Connections? _connections;
  UserSettings? _settings;
  String? _error;
  bool _loading = false;
  bool _googleOAuthPending = false;
  bool _profileSaving = false;
  bool _settingsSaving = false;
  late final TextEditingController _displayNameController;
  late final TextEditingController _timezoneController;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _displayNameController = TextEditingController(
      text: widget.authController.user?.displayName ?? '',
    );
    _timezoneController = TextEditingController(
      text: widget.initialSettings?.timezone ?? '',
    );
    if (widget.initialConnections != null && widget.initialSettings != null) {
      _connections = widget.initialConnections;
      _settings = widget.initialSettings;
      _loading = false;
    } else {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _loadAccountData();
        }
      });
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _displayNameController.dispose();
    _timezoneController.dispose();
    super.dispose();
  }

  bool _lifecyclePaused = false;

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused) {
      _lifecyclePaused = true;
      return;
    }
    if (state == AppLifecycleState.resumed && _lifecyclePaused) {
      _lifecyclePaused = false;
      _loadAccountData();
    }
  }

  Future<void> _loadAccountData() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    Connections? connections;
    UserSettings? settings;
    String? error;
    try {
      connections = await widget.apiClient.getConnections();
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
      return;
    } on ApiException catch (e) {
      error = e.message;
    }
    try {
      settings = await widget.apiClient.getSettings();
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
      return;
    } on ApiException catch (e) {
      error ??= e.message;
    }
    if (mounted) {
      setState(() {
        _connections = connections;
        _settings = settings;
        if (settings != null) {
          _timezoneController.text = settings.timezone;
        }
        _error = error;
        _loading = false;
      });
    }
  }

  Future<void> _saveProfile() async {
    if (_profileSaving) {
      return;
    }
    setState(() => _profileSaving = true);
    try {
      await widget.apiClient.patchMe(displayName: _displayNameController.text.trim());
      await widget.authController.refreshUser();
      if (mounted) {
        setState(() => _error = null);
      }
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (mounted) {
        setState(() => _error = e.message);
      }
    } finally {
      if (mounted) {
        setState(() => _profileSaving = false);
      }
    }
  }

  Future<void> _saveTimezone() async {
    if (_settingsSaving || _settings == null) {
      return;
    }
    setState(() => _settingsSaving = true);
    try {
      final updated = await widget.apiClient.patchSettings(
        timezone: _timezoneController.text.trim(),
      );
      if (mounted) {
        setState(() {
          _settings = updated;
          _error = null;
        });
      }
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (mounted) {
        setState(() => _error = e.message);
      }
    } finally {
      if (mounted) {
        setState(() => _settingsSaving = false);
      }
    }
  }

  Future<void> _saveAiPreferences({
    String? assistantModel,
    String? assistantReasoningEffort,
    String? assistantVerbosity,
  }) async {
    if (_settingsSaving) {
      return;
    }
    setState(() => _settingsSaving = true);
    try {
      final updated = await widget.apiClient.patchSettings(
        assistantModel: assistantModel,
        assistantReasoningEffort: assistantReasoningEffort,
        assistantVerbosity: assistantVerbosity,
      );
      if (mounted) {
        setState(() {
          _settings = updated;
          _error = null;
        });
      }
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (mounted) {
        setState(() => _error = e.message);
      }
    } finally {
      if (mounted) {
        setState(() => _settingsSaving = false);
      }
    }
  }

  Future<void> _showOpenAiKeyDialog({required bool replace}) async {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => _OpenAiKeyDialog(
        apiClient: widget.apiClient,
        authController: widget.authController,
        replace: replace,
        onUpdated: _loadAccountData,
      ),
    );
  }

  Future<void> _deleteOpenAiKey() async {
    try {
      await widget.apiClient.deleteOpenaiCredential();
      await _loadAccountData();
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      if (mounted) {
        setState(() => _error = e.message);
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
        onConnected: _loadAccountData,
      ),
    );
  }

  Future<void> _showConnectYandexDialog() async {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => _YandexConnectDialog(
        apiClient: widget.apiClient,
        authController: widget.authController,
        onConnected: _loadAccountData,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final settings = _settings;

    return Scaffold(
      appBar: AppBar(title: const Text('Аккаунт')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Профиль', style: Theme.of(context).textTheme.titleSmall),
          TextField(
            controller: _displayNameController,
            decoration: const InputDecoration(labelText: 'Отображаемое имя'),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _timezoneController,
            decoration: const InputDecoration(labelText: 'Часовой пояс (IANA)'),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              FilledButton(
                onPressed: _profileSaving ? null : _saveProfile,
                child: Text(_profileSaving ? 'Сохранение…' : 'Сохранить имя'),
              ),
              const SizedBox(width: 8),
              OutlinedButton(
                onPressed: _settingsSaving ? null : _saveTimezone,
                child: Text(_settingsSaving ? 'Сохранение…' : 'Сохранить часовой пояс'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text('ИИ', style: Theme.of(context).textTheme.titleSmall),
          if (settings != null) ...[
            Text(
              settings.openaiKeyConfigured
                  ? 'OpenAI API key: настроен'
                  : 'OpenAI API key: не настроен',
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (!settings.openaiKeyConfigured)
                  OutlinedButton(
                    onPressed: () => _showOpenAiKeyDialog(replace: false),
                    child: const Text('Установить ключ'),
                  ),
                if (settings.openaiKeyConfigured)
                  OutlinedButton(
                    onPressed: () => _showOpenAiKeyDialog(replace: true),
                    child: const Text('Заменить ключ'),
                  ),
                if (settings.openaiKeyConfigured)
                  OutlinedButton(
                    onPressed: _deleteOpenAiKey,
                    child: const Text('Удалить ключ'),
                  ),
              ],
            ),
            Row(
              children: [
                const Text('Модель Assistant:'),
                const SizedBox(width: 8),
                DropdownButton<String>(
                  value: _dropdownAssistantModel(settings),
                  items: settings.allowedAssistantModels
                      .map((model) => DropdownMenuItem(value: model, child: Text(model)))
                      .toList(),
                  onChanged: _settingsSaving
                      ? null
                      : (value) {
                          if (value != null) {
                            _saveAiPreferences(assistantModel: value);
                          }
                        },
                ),
              ],
            ),
            Row(
              children: [
                const Text('Reasoning effort:'),
                const SizedBox(width: 8),
                DropdownButton<String>(
                  value: _dropdownReasoningEffort(settings),
                  items: const [
                    DropdownMenuItem(value: 'none', child: Text('none')),
                    DropdownMenuItem(value: 'low', child: Text('low')),
                    DropdownMenuItem(value: 'medium', child: Text('medium')),
                    DropdownMenuItem(value: 'high', child: Text('high')),
                  ],
                  onChanged: _settingsSaving
                      ? null
                      : (value) {
                          if (value != null) {
                            _saveAiPreferences(assistantReasoningEffort: value);
                          }
                        },
                ),
              ],
            ),
            Row(
              children: [
                const Text('Verbosity:'),
                const SizedBox(width: 8),
                DropdownButton<String>(
                  value: _dropdownVerbosity(settings),
                  items: const [
                    DropdownMenuItem(value: 'low', child: Text('low')),
                    DropdownMenuItem(value: 'medium', child: Text('medium')),
                    DropdownMenuItem(value: 'high', child: Text('high')),
                  ],
                  onChanged: _settingsSaving
                      ? null
                      : (value) {
                          if (value != null) {
                            _saveAiPreferences(assistantVerbosity: value);
                          }
                        },
                ),
              ],
            ),
          ],
          const SizedBox(height: 16),
          Text('Подключения', style: Theme.of(context).textTheme.titleSmall),
          if (_error != null)
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          if (_loading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (_connections != null)
            _ConnectionsList(
              connections: _connections!,
              googleOAuthPending: _googleOAuthPending,
              onConnectGoogle: _startGoogleOAuth,
              onConnectYandex: _showConnectYandexDialog,
              onConnectMattermost: _showConnectMattermostDialog,
            ),
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

String _dropdownAssistantModel(UserSettings settings) {
  if (settings.allowedAssistantModels.contains(settings.assistantModel)) {
    return settings.assistantModel;
  }
  if (settings.allowedAssistantModels.isNotEmpty) {
    return settings.allowedAssistantModels.first;
  }
  return settings.assistantModel;
}

String _dropdownReasoningEffort(UserSettings settings) {
  const allowed = ['none', 'low', 'medium', 'high'];
  if (allowed.contains(settings.assistantReasoningEffort)) {
    return settings.assistantReasoningEffort;
  }
  return 'low';
}

String _dropdownVerbosity(UserSettings settings) {
  const allowed = ['low', 'medium', 'high'];
  if (allowed.contains(settings.assistantVerbosity)) {
    return settings.assistantVerbosity;
  }
  return 'low';
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

String yandexConnectButtonLabel(Connections connections) {
  if (!connections.yandexMail.connected && !connections.yandexCalendar.connected) {
    return 'Подключить Яндекс';
  }
  return 'Обновить данные Яндекса';
}

class _ConnectionsList extends StatelessWidget {
  const _ConnectionsList({
    required this.connections,
    required this.googleOAuthPending,
    required this.onConnectGoogle,
    required this.onConnectYandex,
    required this.onConnectMattermost,
  });

  final Connections connections;
  final bool googleOAuthPending;
  final VoidCallback onConnectGoogle;
  final VoidCallback onConnectYandex;
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
        const SizedBox(height: 8),
        OutlinedButton(
          onPressed: onConnectYandex,
          child: Text(yandexConnectButtonLabel(connections)),
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

class _YandexConnectDialog extends StatefulWidget {
  const _YandexConnectDialog({
    required this.apiClient,
    required this.authController,
    required this.onConnected,
  });

  final SecretaryApiClient apiClient;
  final AuthController authController;
  final Future<void> Function() onConnected;

  @override
  State<_YandexConnectDialog> createState() => _YandexConnectDialogState();
}

class _YandexConnectDialogState extends State<_YandexConnectDialog> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _connectMail = true;
  bool _connectCalendar = true;
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_submitting) {
      return;
    }
    final email = _emailController.text.trim();
    final appPassword = _passwordController.text.trim();
    if (email.isEmpty || appPassword.isEmpty) {
      setState(() {
        _error = 'Укажите email и пароль приложения';
      });
      return;
    }
    if (!_connectMail && !_connectCalendar) {
      setState(() {
        _error = 'Выберите хотя бы один сервис';
      });
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });

    final errors = <String>[];

    if (_connectMail) {
      try {
        await widget.apiClient.connectYandexMail(
          email: email,
          appPassword: appPassword,
        );
      } on AuthenticationException {
        widget.authController.handleAuthenticationFailure();
        if (mounted) {
          Navigator.of(context).pop();
        }
        return;
      } on ApiException catch (e) {
        errors.add('Не удалось подключить Яндекс Почту: ${e.message}');
      }
    }

    if (_connectCalendar) {
      try {
        await widget.apiClient.connectYandexCalendar(
          email: email,
          appPassword: appPassword,
        );
      } on AuthenticationException {
        widget.authController.handleAuthenticationFailure();
        if (mounted) {
          Navigator.of(context).pop();
        }
        return;
      } on ApiException catch (e) {
        errors.add('Не удалось подключить Яндекс Календарь: ${e.message}');
      }
    }

    _passwordController.clear();
    await widget.onConnected();

    if (!mounted) {
      return;
    }

    if (errors.isEmpty) {
      Navigator.of(context).pop();
      return;
    }

    setState(() {
      _error = errors.join('\n');
      _submitting = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Подключить Яндекс'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _emailController,
              decoration: const InputDecoration(
                labelText: 'Email',
                hintText: 'user@yandex.ru',
              ),
              enabled: !_submitting,
              keyboardType: TextInputType.emailAddress,
              textInputAction: TextInputAction.next,
              autocorrect: false,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _passwordController,
              decoration: const InputDecoration(
                labelText: 'Пароль приложения',
              ),
              enabled: !_submitting,
              obscureText: true,
              autocorrect: false,
              enableSuggestions: false,
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _submit(),
            ),
            const SizedBox(height: 12),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Яндекс Почта'),
              value: _connectMail,
              onChanged: _submitting
                  ? null
                  : (value) => setState(() => _connectMail = value ?? false),
            ),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Яндекс Календарь'),
              value: _connectCalendar,
              onChanged: _submitting
                  ? null
                  : (value) => setState(() => _connectCalendar = value ?? false),
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

class _OpenAiKeyDialog extends StatefulWidget {
  const _OpenAiKeyDialog({
    required this.apiClient,
    required this.authController,
    required this.replace,
    required this.onUpdated,
  });

  final SecretaryApiClient apiClient;
  final AuthController authController;
  final bool replace;
  final Future<void> Function() onUpdated;

  @override
  State<_OpenAiKeyDialog> createState() => _OpenAiKeyDialogState();
}

class _OpenAiKeyDialogState extends State<_OpenAiKeyDialog> {
  final _keyController = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _keyController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_submitting) {
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.apiClient.putOpenaiCredential(_keyController.text);
      _keyController.clear();
      await widget.onUpdated();
      if (mounted) {
        Navigator.of(context).pop();
      }
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
      if (mounted) {
        Navigator.of(context).pop();
      }
    } on ApiException catch (e) {
      _keyController.clear();
      if (mounted) {
        setState(() => _error = e.message);
      }
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.replace ? 'Заменить OpenAI ключ' : 'Установить OpenAI ключ'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: _keyController,
            decoration: const InputDecoration(labelText: 'API key'),
            obscureText: true,
            autocorrect: false,
            enableSuggestions: false,
            enabled: !_submitting,
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: _submitting ? null : () => Navigator.of(context).pop(),
          child: const Text('Отмена'),
        ),
        FilledButton(
          onPressed: _submitting ? null : _submit,
          child: Text(widget.replace ? 'Заменить' : 'Установить'),
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
