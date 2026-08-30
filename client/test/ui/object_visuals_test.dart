import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/ui/object_visuals.dart';

void main() {
  test('known object kind icon and label', () {
    expect(iconForKind('task'), isNotNull);
    expect(objectKindLabel('email'), 'Письмо');
    expect(iconForKind('unknown_kind'), isNotNull);
    expect(objectKindLabel('unknown_kind'), 'unknown_kind');
  });

  test('provider labels', () {
    expect(providerLabel('gmail'), 'Gmail');
    expect(providerLabel('yandex_mail'), 'Яндекс');
    expect(providerLabel('local_device'), 'Компьютер');
    expect(providerLabel('upload'), 'Загрузка');
    expect(providerLabel('web'), 'Веб');
    expect(providerLabel('custom_provider'), 'custom_provider');
    expect(providerLabel(null), '');
  });
}
