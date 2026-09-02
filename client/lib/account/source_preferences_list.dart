import 'package:flutter/material.dart';

import '../api/api_models.dart';
import 'source_sync_interval_format.dart';

const Map<String, String> sourcePreferenceLabels = {
  'gmail': 'Gmail',
  'google_calendar': 'Google Календарь',
  'yandex_mail': 'Яндекс Почта',
  'yandex_calendar': 'Яндекс Календарь',
  'mattermost': 'Mattermost',
};

bool sourcePreferenceConnected(String source, Connections connections) {
  switch (source) {
    case 'gmail':
      return connections.google.gmailAvailable;
    case 'google_calendar':
      return connections.google.calendarAvailable;
    case 'yandex_mail':
      return connections.yandexMail.connected;
    case 'yandex_calendar':
      return connections.yandexCalendar.connected;
    case 'mattermost':
      return connections.mattermost.isNotEmpty;
    default:
      return false;
  }
}

String sourcePreferenceLabel(String source) =>
    sourcePreferenceLabels[source] ?? source;

class SourcePreferencesList extends StatelessWidget {
  const SourcePreferencesList({
    super.key,
    required this.preferences,
    required this.connections,
    required this.savingSources,
    required this.rowErrors,
    required this.onToggleEnabled,
    required this.onCadenceChanged,
    required this.onReset,
  });

  final List<SourcePreference> preferences;
  final Connections connections;
  final Set<String> savingSources;
  final Map<String, String> rowErrors;
  final Future<void> Function(String source, bool enabled) onToggleEnabled;
  final Future<void> Function(String source, int seconds) onCadenceChanged;
  final Future<void> Function(String source) onReset;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: preferences.map((preference) {
        final saving = savingSources.contains(preference.source);
        final connected = sourcePreferenceConnected(
          preference.source,
          connections,
        );
        final choices = availableSyncIntervalChoices(
          currentSeconds: preference.syncIntervalSeconds,
          minSeconds: preference.minSyncIntervalSeconds,
          maxSeconds: preference.maxSyncIntervalSeconds,
        );
        final rowError = rowErrors[preference.source];

        return Padding(
          key: Key('source-preference-${preference.source}'),
          padding: const EdgeInsets.only(bottom: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      sourcePreferenceLabel(preference.source),
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                  ),
                  if (!connected)
                    Text(
                      'Не подключено',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  if (saving) ...[
                    const SizedBox(width: 8),
                    const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  ],
                ],
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Синхронизация включена'),
                value: preference.enabled,
                onChanged: saving
                    ? null
                    : (value) => onToggleEnabled(preference.source, value),
              ),
              Row(
                children: [
                  const Text('Интервал:'),
                  const SizedBox(width: 8),
                  DropdownButton<int>(
                    value: preference.syncIntervalSeconds,
                    items: choices
                        .map(
                          (seconds) => DropdownMenuItem(
                            value: seconds,
                            child: Text(formatSyncIntervalSeconds(seconds)),
                          ),
                        )
                        .toList(),
                    onChanged: saving
                        ? null
                        : (value) {
                            if (value != null &&
                                value != preference.syncIntervalSeconds) {
                              onCadenceChanged(preference.source, value);
                            }
                          },
                  ),
                ],
              ),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton(
                  onPressed: saving ? null : () => onReset(preference.source),
                  child: const Text('По умолчанию'),
                ),
              ),
              if (rowError != null)
                Text(
                  rowError,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
            ],
          ),
        );
      }).toList(),
    );
  }
}
