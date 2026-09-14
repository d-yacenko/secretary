import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../assistant/voice_output_policy.dart';
import '../assistant/voice_output_policy_controller.dart';
import 'account_layout.dart';

bool voiceOutputPolicySettingsVisible({TargetPlatform? platform}) {
  final resolved = platform ?? defaultTargetPlatform;
  return resolved == TargetPlatform.android || resolved == TargetPlatform.linux;
}

class VoiceOutputPolicyAccountSection extends StatelessWidget {
  const VoiceOutputPolicyAccountSection({
    super.key,
    required this.controller,
    this.platform,
  });

  final VoiceOutputPolicyController controller;
  final TargetPlatform? platform;

  @override
  Widget build(BuildContext context) {
    if (!voiceOutputPolicySettingsVisible(platform: platform)) {
      return const SizedBox.shrink();
    }
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        return AccountSectionCard(
          key: const Key('voice_output_policy_section'),
          title: 'Автоозвучивание ответов',
          children: [
            RadioListTile<VoiceOutputPolicy>(
              key: const Key('voice_output_policy_hands_free_only'),
              contentPadding: EdgeInsets.zero,
              title: const Text('Только hands-free'),
              subtitle: const Text(
                'Кнопка и системный помощник. Экранный микрофон остаётся '
                'текстом — удобно в офисе.',
              ),
              value: VoiceOutputPolicy.handsFreeOnly,
              groupValue: controller.policy,
              onChanged: (value) {
                if (value != null) {
                  controller.setPolicy(value);
                }
              },
            ),
            RadioListTile<VoiceOutputPolicy>(
              key: const Key('voice_output_policy_all_voice_input'),
              contentPadding: EdgeInsets.zero,
              title: const Text('После любого голосового ввода'),
              subtitle: const Text(
                'Озвучивать ответы и после экранного микрофона.',
              ),
              value: VoiceOutputPolicy.allVoiceInput,
              groupValue: controller.policy,
              onChanged: (value) {
                if (value != null) {
                  controller.setPolicy(value);
                }
              },
            ),
            RadioListTile<VoiceOutputPolicy>(
              key: const Key('voice_output_policy_never'),
              contentPadding: EdgeInsets.zero,
              title: const Text('Никогда'),
              subtitle: const Text(
                'Голосовой ввод остаётся, ответы только текстом.',
              ),
              value: VoiceOutputPolicy.never,
              groupValue: controller.policy,
              onChanged: (value) {
                if (value != null) {
                  controller.setPolicy(value);
                }
              },
            ),
          ],
        );
      },
    );
  }
}
