import 'package:flutter/material.dart';

import '../assistant/system_assistant_bridge.dart';
import 'account_layout.dart';

class SystemAssistantAccountSection extends StatelessWidget {
  const SystemAssistantAccountSection({
    super.key,
    required this.controller,
    this.platform,
  });

  final SystemAssistantController controller;
  final TargetPlatform? platform;

  @override
  Widget build(BuildContext context) {
    if (!systemAssistantSettingsVisible(platform: platform)) {
      return const SizedBox.shrink();
    }
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        return AccountSectionCard(
          key: const Key('system_assistant_section'),
          title: 'Системный помощник',
          children: [
            Text(
              controller.isDefaultAssistant
                  ? 'Секретарь выбран системным помощником'
                  : 'Секретарь не выбран системным помощником',
              key: const Key('system_assistant_status'),
            ),
            const SizedBox(height: 8),
            const Text(
              'Чтобы вызывать голос с кнопки ассистента, с фона и с экрана '
              'блокировки, выберите Секретарь цифровым помощником в Android. '
              'Двойное нажатие «Громкость +» работает только в открытом приложении.',
            ),
            const SizedBox(height: 12),
            OutlinedButton(
              key: const Key('system_assistant_request_role'),
              onPressed: controller.requestAssistantRole,
              child: const Text('Выбрать Секретарь помощником…'),
            ),
            const SizedBox(height: 8),
            SwitchListTile(
              key: const Key('system_assistant_lock_screen'),
              contentPadding: EdgeInsets.zero,
              title: const Text('Голос с заблокированного экрана'),
              subtitle: const Text(
                'Без PIN можно начать голосовой ход. Отправка писем и сообщений '
                'по-прежнему требует разблокировки.',
              ),
              value: controller.lockScreenVoiceEnabled,
              onChanged: controller.setLockScreenVoiceEnabled,
            ),
          ],
        );
      },
    );
  }
}
