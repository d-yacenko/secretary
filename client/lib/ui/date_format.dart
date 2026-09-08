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

const _monthGenitive = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
];

const _weekdays = [
  'понедельник',
  'вторник',
  'среда',
  'четверг',
  'пятница',
  'суббота',
  'воскресенье',
];

String formatRussianNumericDate(DateTime local, {bool twoDigitYear = true}) {
  final day = local.day.toString().padLeft(2, '0');
  final month = local.month.toString().padLeft(2, '0');
  if (twoDigitYear) {
    final year = (local.year % 100).toString().padLeft(2, '0');
    return '$day.$month.$year';
  }
  return '$day.$month.${local.year}';
}

String formatRussianClockTime(DateTime local) {
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  return '$hour:$minute';
}

String formatRussianDayMonth(DateTime local, {bool padDay = false}) {
  final day = padDay ? local.day.toString().padLeft(2, '0') : '${local.day}';
  return '$day ${_monthGenitive[local.month - 1]}';
}

String formatRussianWeekday(DateTime local) => _weekdays[local.weekday - 1];

