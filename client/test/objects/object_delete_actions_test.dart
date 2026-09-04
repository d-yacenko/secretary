import 'package:flutter_test/flutter_test.dart';

import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/objects/object_delete_actions.dart';

void main() {
  test('delete confirmation for local file mentions device', () {
    final object = SecretaryObject(
      id: '1',
      kind: 'file',
      title: 'Local doc',
      provider: 'local_device',
      metadata: const {},
      origin: 'explicit',
      state: 'confirmed',
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
    );
    expect(
      deleteConfirmationMessage(object),
      contains('устройстве'),
    );
  });

  test('delete confirmation for note is secretary-only', () {
    final object = SecretaryObject(
      id: '2',
      kind: 'note',
      title: 'Note',
      metadata: const {},
      origin: 'user',
      state: 'confirmed',
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
    );
    expect(deleteConfirmationMessage(object), 'Удалить из Секретаря?');
    expect(deleteConfirmationMessage(object), isNot(contains('Gmail')));
  });
}
