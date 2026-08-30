import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/graph/graph_layout.dart';

SecretaryObject _ringObject(String id, String title) {
  return SecretaryObject(
    id: id,
    kind: 'email',
    title: title,
    metadata: {},
    origin: 'source',
    state: 'observed',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
  );
}

SecretaryObject _rootObject() {
  return SecretaryObject(
    id: 'root',
    kind: 'task',
    title: 'Root',
    metadata: {},
    origin: 'user',
    state: 'confirmed',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
  );
}

void _expectNoOverlaps(Map<String, Offset> positions, {String? reason}) {
  final ids = positions.keys.toList();
  for (var i = 0; i < ids.length; i++) {
    for (var j = i + 1; j < ids.length; j++) {
      expect(
        GraphLayout.nodeRectsOverlap(positions[ids[i]]!, positions[ids[j]]!),
        isFalse,
        reason: '${reason ?? ''} overlap between ${ids[i]} and ${ids[j]}',
      );
    }
  }
}

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

  test('fit single node centers in viewport using canvas coordinates', () {
    final positions = {'root': const Offset(0, 0)};
    final viewport = const Size(400, 300);
    final bounds = GraphLayout.viewportBoundsAfterFit(
      positions: positions,
      viewportSize: viewport,
    );

    expect(bounds.left, greaterThanOrEqualTo(0));
    expect(bounds.top, greaterThanOrEqualTo(0));
    expect(bounds.right, lessThanOrEqualTo(viewport.width));
    expect(bounds.bottom, lessThanOrEqualTo(viewport.height));
    expect(bounds.center.dx, closeTo(viewport.width / 2, 2.0));
    expect(bounds.center.dy, closeTo(viewport.height / 2, 2.0));
  });

  test('fit ring with negative raw coordinates stays inside viewport', () {
    final positions = {
      'root': const Offset(-200, -150),
      'a': const Offset(-20, -150),
      'b': const Offset(-200, -30),
    };
    final viewport = const Size(500, 400);
    final bounds = GraphLayout.viewportBoundsAfterFit(
      positions: positions,
      viewportSize: viewport,
    );

    expect(bounds.left, greaterThanOrEqualTo(0));
    expect(bounds.top, greaterThanOrEqualTo(0));
    expect(bounds.right, lessThanOrEqualTo(viewport.width));
    expect(bounds.bottom, lessThanOrEqualTo(viewport.height));
  });

  test('fit uses provided viewport width not a wider screen width', () {
    final positions = {
      'root': const Offset(0, 0),
      'a': const Offset(220, 40),
    };
    final canvasViewport = const Size(320, 400);
    final screenViewport = const Size(920, 400);
    final canvasFit = GraphLayout.viewportBoundsAfterFit(
      positions: positions,
      viewportSize: canvasViewport,
    );
    final screenFit = GraphLayout.viewportBoundsAfterFit(
      positions: positions,
      viewportSize: screenViewport,
    );

    expect(canvasFit.width, lessThan(screenFit.width));
  });

  test('fit clamps to shared scale range for large bounded overview graph', () {
    final positions = <String, Offset>{};
    for (var index = 0; index < 16; index++) {
      positions['wide-$index'] = Offset(index * 180.0, (index % 4) * 200.0);
    }
    final viewport = const Size(320, 500);
    final canvasBounds = GraphLayout.canvasBoundsFromPositions(positions);
    final naturalScale = math.min(
      (viewport.width - kGraphCanvasPadding * 2) / canvasBounds.width,
      (viewport.height - kGraphCanvasPadding * 2) / canvasBounds.height,
    );
    expect(naturalScale, lessThan(0.2));

    final transform = GraphLayout.fitTransform(
      positions: positions,
      viewportSize: viewport,
    );
    final scale = transform.getMaxScaleOnAxis();
    expect(scale, greaterThanOrEqualTo(kGraphMinScale));
    expect(scale, lessThanOrEqualTo(kGraphMaxScale));

    final bounds = GraphLayout.viewportBoundsAfterFit(
      positions: positions,
      viewportSize: viewport,
    );
    expect(bounds.left, greaterThanOrEqualTo(0));
    expect(bounds.top, greaterThanOrEqualTo(0));
    expect(bounds.right, lessThanOrEqualTo(viewport.width));
    expect(bounds.bottom, lessThanOrEqualTo(viewport.height));
  });

  test('computeEdgeEndpoints connects node borders not centers', () {
    final endpoints = GraphLayout.computeEdgeEndpoints(
      sourceCenter: const Offset(0, 0),
      targetCenter: const Offset(200, 0),
    );
    expect(endpoints.start.dx, closeTo(kGraphNodeWidth / 2, 0.01));
    expect(endpoints.start.dy, closeTo(0, 0.01));
    expect(endpoints.end.dx, closeTo(200 - kGraphNodeWidth / 2, 0.01));
    expect(endpoints.end.dy, closeTo(0, 0.01));
  });

  test('overview layout does not overlap fixed-size node cards', () {
    final nodes = List.generate(
      16,
      (index) => SecretaryObject(
        id: 'node-$index',
        kind: 'task',
        title: 'Task $index',
        metadata: {},
        origin: 'user',
        state: 'confirmed',
        createdAt: '2026-01-01T00:00:00Z',
        updatedAt: '2026-01-01T00:00:00Z',
      ),
    );
    final positions = GraphLayout.computePositions(
      nodes: nodes,
      rootId: null,
      existing: {},
      freshRoot: true,
    );
    final ids = positions.keys.toList();
    for (var i = 0; i < ids.length; i++) {
      for (var j = i + 1; j < ids.length; j++) {
        expect(
          GraphLayout.nodeRectsOverlap(positions[ids[i]]!, positions[ids[j]]!),
          isFalse,
          reason: 'overlap between ${ids[i]} and ${ids[j]}',
        );
      }
    }
  });

  test('rooted ring layout does not overlap for neighbor counts 1..24', () {
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

    for (var count = 1; count <= 24; count++) {
      final ring = List.generate(
        count,
        (index) => SecretaryObject(
          id: 'ring-$index',
          kind: 'email',
          title: 'Email $index',
          metadata: {},
          origin: 'source',
          state: 'observed',
          createdAt: '2026-01-01T00:00:00Z',
          updatedAt: '2026-01-01T00:00:00Z',
        ),
      );
      final positions = GraphLayout.computePositions(
        nodes: [root, ...ring],
        rootId: 'root',
        existing: {},
        freshRoot: true,
      );
      final ids = positions.keys.toList();
      for (var i = 0; i < ids.length; i++) {
        for (var j = i + 1; j < ids.length; j++) {
          expect(
            GraphLayout.nodeRectsOverlap(positions[ids[i]]!, positions[ids[j]]!),
            isFalse,
            reason: 'count=$count overlap between ${ids[i]} and ${ids[j]}',
          );
        }
      }
    }
  });

  test('incremental placement keeps existing neighbors and avoids overlap', () {
    final root = _rootObject();
    final a = _ringObject('a', 'A');
    final b = _ringObject('b', 'B');

    final initial = GraphLayout.computePositions(
      nodes: [root, a],
      rootId: 'root',
      existing: {},
      freshRoot: true,
    );
    final rootPos = initial['root']!;
    final aPos = initial['a']!;

    final expanded = GraphLayout.computePositions(
      nodes: [root, a, b],
      rootId: 'root',
      existing: initial,
      freshRoot: false,
    );

    expect(expanded['root'], rootPos);
    expect(expanded['a'], aPos);
    expect(expanded.containsKey('b'), isTrue);
    expect(
      GraphLayout.nodeRectsOverlap(expanded['root']!, expanded['b']!),
      isFalse,
    );
    expect(
      GraphLayout.nodeRectsOverlap(expanded['a']!, expanded['b']!),
      isFalse,
    );
  });

  test('incremental neighbor addition up to 24 preserves positions and avoids overlap', () {
    final root = _rootObject();
    var positions = GraphLayout.computePositions(
      nodes: [root],
      rootId: 'root',
      existing: {},
      freshRoot: true,
    );
    final neighbors = <SecretaryObject>[];

    for (var index = 0; index < 24; index++) {
      final neighbor = _ringObject('n-$index', 'Neighbor $index');
      neighbors.add(neighbor);
      final before = Map<String, Offset>.from(positions);
      positions = GraphLayout.computePositions(
        nodes: [root, ...neighbors],
        rootId: 'root',
        existing: positions,
        freshRoot: false,
      );
      for (final entry in before.entries) {
        expect(
          positions[entry.key],
          entry.value,
          reason: 'position changed for ${entry.key} at index $index',
        );
      }
      _expectNoOverlaps(positions, reason: 'index=$index');
    }
  });
}
