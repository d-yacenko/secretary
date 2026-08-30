String formatUserDateTime(String? iso) {
  if (iso == null || iso.trim().isEmpty) {
    return '';
  }
  final parsed = DateTime.tryParse(iso);
  if (parsed == null) {
    return iso;
  }
  final local = parsed.toLocal();
  final day = local.day.toString().padLeft(2, '0');
  final month = local.month.toString().padLeft(2, '0');
  final year = local.year.toString();
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  return '$day.$month.$year, $hour:$minute';
}

String formatUserDateTimeFromDateTime(DateTime? value) {
  if (value == null) {
    return '';
  }
  return formatUserDateTime(value.toUtc().toIso8601String());
}

String formatUserTime(String? iso) {
  if (iso == null || iso.trim().isEmpty) {
    return '';
  }
  final parsed = DateTime.tryParse(iso);
  if (parsed == null) {
    return iso;
  }
  final local = parsed.toLocal();
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  return '$hour:$minute';
}
