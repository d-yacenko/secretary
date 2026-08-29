import '../api/api_models.dart';

String notificationEvidenceLabel(NotificationOut notification) {
  final evidence = notification.proposal['evidence'];
  if (evidence is List && evidence.isNotEmpty) {
    final first = evidence.first;
    if (first is Map<String, dynamic>) {
      final parts = <String>[];
      final kind = first['kind'] as String?;
      final title = first['title'] as String?;
      final why = first['why_included'] as String?;
      if (kind != null && kind.isNotEmpty) {
        parts.add(kind);
      }
      if (title != null && title.isNotEmpty) {
        parts.add(title);
      }
      if (parts.isNotEmpty) {
        return parts.join(' / ');
      }
      if (why != null && why.isNotEmpty) {
        return why;
      }
    }
  }

  final proposalType = notification.proposalType;
  if (proposalType != null && proposalType.isNotEmpty) {
    return proposalType;
  }
  return 'Notification';
}

bool notificationIsUrgent(NotificationOut notification) {
  return notification.priority == 'urgent' || notification.priority == 'high';
}
