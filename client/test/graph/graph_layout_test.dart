import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/graph/graph_layout.dart';

void main() {
  test('fresh root centers even when existing is empty', () {
    final root = SecretaryObject(
      id: 'root',
      kind: 'task',
      title: 'Root',
      metadata: {},
      origin: 'user',
      state: 'confirmed',
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
    );
    final a = SecretaryObject(
      id: 'a',
      kind: 'note',
      title: 'A',
      metadata: {},
      origin: 'user',
      state: 'confirmed',
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
    );
    final b = SecretaryObject(
      id: 'b',
      kind: 'note',
      title: 'B',
      metadata: {},
      origin: 'user',
      state: 'confirmed',
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
    );

    final positions = GraphLayout.computePositions(
      nodes: [root, a, b],
      rootId: 'root',
      existing: {},
      freshRoot: true,
    );

    expect(positions['root'], const Offset(0, 0));
    expect(positions.containsKey('a'), isTrue);
    expect(positions.containsKey('b'), isTrue);
    expect(positions['a']!.dx, isNot(0));
    expect(positions['b']!.dx, isNot(0));
  });

  test('expand preserves existing root position', () {
    final root = SecretaryObject(
      id: 'root',
      kind: 'task',
      title: 'Root',
      metadata: {},
      origin: 'user',
      state: 'confirmed',
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
    );
    final newcomer = SecretaryObject(
      id: 'new',
      kind: 'note',
      title: 'New',
      metadata: {},
      origin: 'user',
      state: 'confirmed',
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
    );
    final existing = {'root': const Offset(42, 17)};

    final positions = GraphLayout.computePositions(
      nodes: [root, newcomer],
      rootId: 'root',
      existing: existing,
      freshRoot: false,
    );

    expect(positions['root'], const Offset(42, 17));
    expect(positions.containsKey('new'), isTrue);
  });
}
