import 'package:flutter/material.dart';

import 'app_spacing.dart';
import 'object_presentation.dart';

class ProviderVisual {
  const ProviderVisual({
    required this.icon,
    required this.color,
    required this.label,
  });

  final IconData icon;
  final Color color;
  final String label;
}

ProviderVisual providerVisual(String? provider) {
  final key = provider?.trim() ?? '';
  switch (key) {
    case 'gmail':
      return ProviderVisual(
        icon: Icons.mail,
        color: const Color(0xFFEA4335),
        label: providerLabel(key),
      );
    case 'google_calendar':
      return ProviderVisual(
        icon: Icons.calendar_month,
        color: const Color(0xFF4285F4),
        label: providerLabel(key),
      );
    case 'google_drive':
      return ProviderVisual(
        icon: Icons.cloud,
        color: const Color(0xFF0F9D58),
        label: providerLabel(key),
      );
    case 'google':
      return ProviderVisual(
        icon: Icons.apps,
        color: const Color(0xFF4285F4),
        label: providerLabel(key),
      );
    case 'yandex_mail':
      return ProviderVisual(
        icon: Icons.alternate_email,
        color: const Color(0xFFFC3F1D),
        label: providerLabel(key),
      );
    case 'yandex_calendar':
      return ProviderVisual(
        icon: Icons.event,
        color: const Color(0xFFFFCC00),
        label: providerLabel(key),
      );
    case 'yandex_disk':
      return ProviderVisual(
        icon: Icons.cloud_queue,
        color: const Color(0xFFFFCC00),
        label: providerLabel(key),
      );
    case 'yandex':
      return ProviderVisual(
        icon: Icons.alternate_email,
        color: const Color(0xFFFC3F1D),
        label: providerLabel(key),
      );
    case 'mattermost':
      return ProviderVisual(
        icon: Icons.forum,
        color: const Color(0xFF0058CC),
        label: providerLabel(key),
      );
    case 'local_device':
      return ProviderVisual(
        icon: Icons.computer,
        color: const Color(0xFF5F6368),
        label: providerLabel(key),
      );
    case 'upload':
      return ProviderVisual(
        icon: Icons.upload_file,
        color: const Color(0xFF7B61FF),
        label: providerLabel(key),
      );
    case 'web':
      return ProviderVisual(
        icon: Icons.language,
        color: const Color(0xFF1A73E8),
        label: providerLabel(key),
      );
    default:
      return ProviderVisual(
        icon: Icons.source_outlined,
        color: const Color(0xFF607D8B),
        label: providerLabel(provider),
      );
  }
}

bool providerHasIdentity(String? provider) {
  return provider != null && provider.trim().isNotEmpty;
}

/// Colored compact provider/source icon. Distinct from Object kind icons.
class ProviderSourceIcon extends StatelessWidget {
  const ProviderSourceIcon({
    super.key,
    required this.provider,
    this.size = AppSpacing.providerIconSize,
    this.onPressed,
    this.openTooltip,
  });

  final String? provider;
  final double size;
  final VoidCallback? onPressed;
  final String? openTooltip;

  @override
  Widget build(BuildContext context) {
    if (!providerHasIdentity(provider)) {
      return const SizedBox.shrink();
    }
    final visual = providerVisual(provider);
    final icon = Icon(
      visual.icon,
      size: size,
      color: visual.color,
    );
    final semantics = openTooltip ?? visual.label;
    final labeled = Semantics(
      button: onPressed != null,
      label: semantics,
      child: Tooltip(
        message: semantics,
        child: icon,
      ),
    );
    if (onPressed == null) {
      return KeyedSubtree(
        key: Key('provider_icon_${provider!.trim()}'),
        child: SizedBox(
          width: size,
          height: size,
          child: labeled,
        ),
      );
    }
    final compact = isWideLayout(context);
    return IconButton(
      key: Key('provider_open_${provider!.trim()}'),
      tooltip: openTooltip ?? 'Открыть в источнике',
      onPressed: onPressed,
      visualDensity:
          compact ? VisualDensity.compact : VisualDensity.standard,
      padding: compact ? const EdgeInsets.all(AppSpacing.xs) : null,
      constraints: compact
          ? const BoxConstraints(minWidth: 32, minHeight: 32)
          : const BoxConstraints(minWidth: 40, minHeight: 40),
      icon: icon,
    );
  }
}
