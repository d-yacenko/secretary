import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/ui/object_presentation.dart';
import 'package:personal_secretary/ui/provider_icon.dart';

void main() {
  test('known object kind icon and label', () {
    expect(iconForKind('task'), isNotNull);
    expect(objectKindLabel('email'), 'Письмо');
    expect(iconForKind('folder'), Icons.folder_outlined);
    expect(objectKindLabel('folder'), 'Папка');
    expect(iconForKind('unknown_kind'), isNotNull);
    expect(objectKindLabel('unknown_kind'), 'unknown_kind');
  });

  test('provider labels', () {
    expect(providerLabel('gmail'), 'Gmail');
    expect(providerLabel('yandex_mail'), 'Яндекс');
    expect(providerLabel('yandex_calendar'), 'Яндекс Календарь');
    expect(providerLabel('google_calendar'), 'Google Календарь');
    expect(providerLabel('local_device'), 'Компьютер');
    expect(providerLabel('upload'), 'Загрузка');
    expect(providerLabel('web'), 'Веб');
    expect(providerLabel('custom_provider'), 'custom_provider');
    expect(providerLabel(null), 'Источник');
  });

  test('provider compact glyphs remain available as fallback labels', () {
    expect(providerCompactGlyph('yandex_calendar'), 'Я');
    expect(providerCompactGlyph('google_calendar'), 'G');
    expect(providerCompactGlyph('yandex_mail'), 'Я');
    expect(providerCompactGlyph('gmail'), 'G');
    expect(providerCompactGlyph('mattermost'), 'M');
  });

  test('provider visuals use colored icons distinct from kind icons', () {
    expect(providerVisual('gmail').icon, Icons.mail);
    expect(providerVisual('gmail').icon, isNot(iconForKind('email')));
    expect(providerVisual('google_calendar').icon, Icons.calendar_month);
    expect(providerVisual('google_drive').icon, Icons.cloud);
    expect(providerVisual('yandex_mail').icon, Icons.alternate_email);
    expect(providerVisual('yandex_calendar').icon, Icons.event);
    expect(providerVisual('yandex_disk').icon, Icons.cloud_queue);
    expect(providerVisual('mattermost').icon, Icons.forum);
    expect(providerVisual('local_device').icon, Icons.computer);
    expect(providerVisual('upload').icon, Icons.upload_file);
    expect(providerVisual('web').icon, Icons.language);
    expect(providerVisual('unknown-source').icon, Icons.source_outlined);
    expect(providerVisual('gmail').color, isNot(const Color(0xFF000000)));
  });
}
