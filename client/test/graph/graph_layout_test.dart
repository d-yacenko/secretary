import 'dart:math' as math;
import 'dart:ui';

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
}
