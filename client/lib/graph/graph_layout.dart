import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter/material.dart';

import '../api/api_models.dart';

const double kGraphNodeWidth = 186;
const double kGraphNodeHeight = 100;
const double kGraphNodeHorizontalGap = 24;
const double kGraphNodeVerticalGap = 24;
const int kGraphOverviewColumns = 4;
const double kGraphCanvasPadding = 80;
const double kGraphMinScale = 0.05;
const double kGraphMaxScale = 2.5;

class GraphLayout {
  static double get overviewColumnStep => kGraphNodeWidth + kGraphNodeHorizontalGap;
  static double get overviewRowStep => kGraphNodeHeight + kGraphNodeVerticalGap;

  static Map<String, Offset> computePositions({
    required List<SecretaryObject> nodes,
    required List<SecretaryEdge> edges,
    required String? rootId,
    required Map<String, Offset> existing,
    bool freshRoot = false,
  }) {
    final positions = freshRoot ? <String, Offset>{} : Map<String, Offset>.from(existing);
    final nodeIds = nodes.map((node) => node.id).toSet();
    final sorted = List<SecretaryObject>.from(nodes);
    sorted.sort((a, b) {
      final left = '${a.kind}|${a.title}|${a.id}';
      final right = '${b.kind}|${b.title}|${b.id}';
      return left.compareTo(right);
    });
    final adjacency = _buildAdjacency(edges, nodeIds);

    if (rootId != null && nodeIds.contains(rootId)) {
      _layoutRooted(
        rootId: rootId,
        sorted: sorted,
        nodeIds: nodeIds,
        adjacency: adjacency,
        positions: positions,
        freshRoot: freshRoot,
      );
      return positions;
    }

    _layoutOverview(
      sorted: sorted,
      nodeIds: nodeIds,
      adjacency: adjacency,
      positions: positions,
      freshRoot: freshRoot,
    );
    return positions;
  }

  static Map<String, Set<String>> _buildAdjacency(
    List<SecretaryEdge> edges,
    Set<String> nodeIds,
  ) {
    final adjacency = <String, Set<String>>{for (final id in nodeIds) id: <String>{}};
    for (final edge in edges) {
      if (!nodeIds.contains(edge.sourceId) || !nodeIds.contains(edge.targetId)) {
        continue;
      }
      adjacency[edge.sourceId]!.add(edge.targetId);
      adjacency[edge.targetId]!.add(edge.sourceId);
    }
    return adjacency;
  }

  static Offset _nodeCenter(Offset topLeft) {
    return Offset(
      topLeft.dx + kGraphNodeWidth / 2,
      topLeft.dy + kGraphNodeHeight / 2,
    );
  }

  static Map<String, int> _bfsDistances(
    String start,
    Map<String, Set<String>> adjacency,
    Set<String> nodeIds,
  ) {
    final distances = <String, int>{start: 0};
    final queue = <String>[start];
    while (queue.isNotEmpty) {
      final current = queue.removeAt(0);
      final nextDistance = distances[current]! + 1;
      for (final neighbor in adjacency[current] ?? const <String>{}) {
        if (!nodeIds.contains(neighbor) || distances.containsKey(neighbor)) {
          continue;
        }
        distances[neighbor] = nextDistance;
        queue.add(neighbor);
      }
    }
    for (final id in nodeIds) {
      distances.putIfAbsent(id, () => 9999);
    }
    return distances;
  }

  static void _layoutRooted({
    required String rootId,
    required List<SecretaryObject> sorted,
    required Set<String> nodeIds,
    required Map<String, Set<String>> adjacency,
    required Map<String, Offset> positions,
    required bool freshRoot,
  }) {
    if (!positions.containsKey(rootId)) {
      positions[rootId] = const Offset(0, 0);
    }
    final newcomers = sorted
        .where((node) => node.id != rootId && !positions.containsKey(node.id))
        .toList();
    if (newcomers.isEmpty) {
      return;
    }
    final rootCenter = _nodeCenter(positions[rootId]!);
    if (freshRoot) {
      final distances = _bfsDistances(rootId, adjacency, nodeIds);
      final layers = <int, List<String>>{};
      for (final id in nodeIds) {
        if (id == rootId) {
          continue;
        }
        final layer = distances[id] ?? 9999;
        layers.putIfAbsent(layer, () => <String>[]).add(id);
      }
      final layerKeys = layers.keys.where((layer) => layer > 0 && layer < 9999).toList()
        ..sort();
      final layerStep = _minCenterSeparation();
      for (final layer in layerKeys) {
        final members = layers[layer]!..sort();
        final radius = _ringRadiusForCount(members.length) + (layer - 1) * layerStep;
        final step = (2 * math.pi) / members.length;
        for (var index = 0; index < members.length; index++) {
          final angle = step * index - math.pi / 2;
          final ringCenter = Offset(
            rootCenter.dx + math.cos(angle) * radius,
            rootCenter.dy + math.sin(angle) * radius,
          );
          positions[members[index]] = Offset(
            ringCenter.dx - kGraphNodeWidth / 2,
            ringCenter.dy - kGraphNodeHeight / 2,
          );
        }
      }
      for (final newcomer in newcomers) {
        if (!positions.containsKey(newcomer.id)) {
          positions[newcomer.id] = _findIncrementalRingPosition(
            rootCenter: rootCenter,
            occupied: positions,
          );
        }
      }
      return;
    }
    for (final newcomer in newcomers) {
      final neighbors = adjacency[newcomer.id] ?? const <String>{};
      final anchored = neighbors.where((id) => positions.containsKey(id)).toList()..sort();
      if (anchored.isNotEmpty) {
        var cx = 0.0;
        var cy = 0.0;
        for (final id in anchored) {
          final center = _nodeCenter(positions[id]!);
          cx += center.dx;
          cy += center.dy;
        }
        final anchor = Offset(cx / anchored.length, cy / anchored.length);
        positions[newcomer.id] = _findIncrementalNearCenter(
          anchor: anchor,
          occupied: positions,
        );
      } else {
        positions[newcomer.id] = _findIncrementalRingPosition(
          rootCenter: rootCenter,
          occupied: positions,
        );
      }
    }
  }

  static List<Set<String>> _connectedComponents(
    Set<String> nodeIds,
    Map<String, Set<String>> adjacency,
  ) {
    final remaining = Set<String>.from(nodeIds);
    final components = <Set<String>>[];
    while (remaining.isNotEmpty) {
      final start = remaining.first;
      final component = <String>{};
      final queue = <String>[start];
      while (queue.isNotEmpty) {
        final current = queue.removeAt(0);
        if (!remaining.contains(current)) {
          continue;
        }
        remaining.remove(current);
        component.add(current);
        for (final neighbor in adjacency[current] ?? const <String>{}) {
          if (remaining.contains(neighbor)) {
            queue.add(neighbor);
          }
        }
      }
      components.add(component);
    }
    components.sort((a, b) {
      final aKey = a.reduce((left, right) => left.compareTo(right) <= 0 ? left : right);
      final bKey = b.reduce((left, right) => left.compareTo(right) <= 0 ? left : right);
      return aKey.compareTo(bKey);
    });
    return components;
  }

  static String _pickHub(Set<String> component, Map<String, Set<String>> adjacency) {
    String hub = component.first;
    var bestDegree = -1;
    for (final id in component) {
      final degree = (adjacency[id] ?? const <String>{}).where(component.contains).length;
      if (degree > bestDegree || (degree == bestDegree && id.compareTo(hub) < 0)) {
        hub = id;
        bestDegree = degree;
      }
    }
    return hub;
  }

  static void _layoutOverview({
    required List<SecretaryObject> sorted,
    required Set<String> nodeIds,
    required Map<String, Set<String>> adjacency,
    required Map<String, Offset> positions,
    required bool freshRoot,
  }) {
    final components = _connectedComponents(nodeIds, adjacency);
    var offsetX = 0.0;
    for (final component in components) {
      final componentNodes = sorted.where((node) => component.contains(node.id)).toList();
      final local = <String, Offset>{};
      for (final node in componentNodes) {
        if (positions.containsKey(node.id)) {
          local[node.id] = positions[node.id]!;
        }
      }
      final newcomers = componentNodes.where((node) => !local.containsKey(node.id)).toList();
      if (freshRoot || local.isEmpty) {
        final hub = _pickHub(component, adjacency);
        local[hub] = const Offset(0, 0);
        final distances = _bfsDistances(hub, adjacency, component);
        final layers = <int, List<String>>{};
        for (final id in component) {
          if (id == hub) {
            continue;
          }
          layers.putIfAbsent(distances[id] ?? 9999, () => <String>[]).add(id);
        }
        final hubCenter = _nodeCenter(local[hub]!);
        final layerKeys = layers.keys.where((layer) => layer > 0 && layer < 9999).toList()
          ..sort();
        final layerStep = _minCenterSeparation();
        for (final layer in layerKeys) {
          final members = layers[layer]!..sort();
          final radius = _ringRadiusForCount(members.length) + (layer - 1) * layerStep;
          final step = (2 * math.pi) / members.length;
          for (var index = 0; index < members.length; index++) {
            final angle = step * index - math.pi / 2;
            final ringCenter = Offset(
              hubCenter.dx + math.cos(angle) * radius,
              hubCenter.dy + math.sin(angle) * radius,
            );
            local[members[index]] = Offset(
              ringCenter.dx - kGraphNodeWidth / 2,
              ringCenter.dy - kGraphNodeHeight / 2,
            );
          }
        }
        for (final node in componentNodes) {
          if (!local.containsKey(node.id)) {
            local[node.id] = _findIncrementalNearCenter(
              anchor: hubCenter,
              occupied: local,
            );
          }
        }
      } else {
        for (final newcomer in newcomers) {
          final neighbors = adjacency[newcomer.id] ?? const <String>{};
          final anchored = neighbors.where((id) => local.containsKey(id)).toList()..sort();
          if (anchored.isNotEmpty) {
            var cx = 0.0;
            var cy = 0.0;
            for (final id in anchored) {
              final center = _nodeCenter(local[id]!);
              cx += center.dx;
              cy += center.dy;
            }
            local[newcomer.id] = _findIncrementalNearCenter(
              anchor: Offset(cx / anchored.length, cy / anchored.length),
              occupied: local,
            );
          } else {
            local[newcomer.id] = _findIncrementalNearCenter(
              anchor: _nodeCenter(local.values.first),
              occupied: local,
            );
          }
        }
      }
      final bounds = computeBounds(local);
      final translate = Offset(offsetX - bounds.left, -bounds.top);
      for (final entry in local.entries) {
        positions[entry.key] = entry.value + translate;
      }
      offsetX += bounds.width + overviewColumnStep;
    }
  }

  static double _minCenterSeparation() {
    final sepW = kGraphNodeWidth + kGraphNodeHorizontalGap;
    final sepH = kGraphNodeHeight + kGraphNodeVerticalGap;
    return math.sqrt(sepW * sepW + sepH * sepH);
  }

  static double _ringRadiusForCount(int count) {
    if (count <= 0) {
      return 0;
    }
    final minCenter = _minCenterSeparation();
    final rootClearance = minCenter;
    if (count == 1) {
      return rootClearance;
    }
    final neighborClearance = minCenter / (2 * math.sin(math.pi / count));
    return math.max(rootClearance, neighborClearance);
  }

  static const int _incrementalAngularSlots = 24;
  static const int _incrementalMaxRings = 48;

  static Offset _findIncrementalRingPosition({
    required Offset rootCenter,
    required Map<String, Offset> occupied,
  }) {
    final minCenter = _minCenterSeparation();
    final radiusStep = minCenter;
    final startRadius = _ringRadiusForCount(1);
    final angleStep = (2 * math.pi) / _incrementalAngularSlots;

    for (var ring = 0; ring < _incrementalMaxRings; ring++) {
      final radius = startRadius + ring * radiusStep;
      for (var slot = 0; slot < _incrementalAngularSlots; slot++) {
        final angle = angleStep * slot - math.pi / 2;
        final ringCenter = Offset(
          rootCenter.dx + math.cos(angle) * radius,
          rootCenter.dy + math.sin(angle) * radius,
        );
        final candidate = Offset(
          ringCenter.dx - kGraphNodeWidth / 2,
          ringCenter.dy - kGraphNodeHeight / 2,
        );
        if (!_positionOverlapsAny(candidate, occupied)) {
          return candidate;
        }
      }
    }
    throw StateError('no free incremental graph slot around root');
  }

  static Offset _findIncrementalNearCenter({
    required Offset anchor,
    required Map<String, Offset> occupied,
  }) {
    final minCenter = _minCenterSeparation();
    final radiusStep = minCenter;
    final startRadius = _ringRadiusForCount(1);
    final angleStep = (2 * math.pi) / _incrementalAngularSlots;

    for (var ring = 0; ring < _incrementalMaxRings; ring++) {
      final radius = startRadius + ring * radiusStep;
      for (var slot = 0; slot < _incrementalAngularSlots; slot++) {
        final angle = angleStep * slot - math.pi / 2;
        final ringCenter = Offset(
          anchor.dx + math.cos(angle) * radius,
          anchor.dy + math.sin(angle) * radius,
        );
        final candidate = Offset(
          ringCenter.dx - kGraphNodeWidth / 2,
          ringCenter.dy - kGraphNodeHeight / 2,
        );
        if (!_positionOverlapsAny(candidate, occupied)) {
          return candidate;
        }
      }
    }
    throw StateError('no free incremental graph slot near anchor');
  }

  static bool _positionOverlapsAny(
    Offset position,
    Map<String, Offset> occupied,
  ) {
    for (final other in occupied.values) {
      if (nodeRectsOverlap(position, other)) {
        return true;
      }
    }
    return false;
  }

  static Rect nodeRectAt(Offset position) {
    return Rect.fromLTWH(
      position.dx,
      position.dy,
      kGraphNodeWidth,
      kGraphNodeHeight,
    );
  }

  static bool nodeRectsOverlap(Offset left, Offset right) {
    return nodeRectAt(left).overlaps(nodeRectAt(right));
  }

  /// Bounds of node rectangles in graph coordinates.
  static Rect computeBounds(Map<String, Offset> positions) {
    if (positions.isEmpty) {
      return const Rect.fromLTWH(-100, -100, 200, 200);
    }
    double minX = double.infinity;
    double minY = double.infinity;
    double maxX = -double.infinity;
    double maxY = -double.infinity;
    for (final position in positions.values) {
      minX = math.min(minX, position.dx);
      minY = math.min(minY, position.dy);
      maxX = math.max(maxX, position.dx + kGraphNodeWidth);
      maxY = math.max(maxY, position.dy + kGraphNodeHeight);
    }
    return Rect.fromLTRB(minX, minY, maxX, maxY);
  }

  /// Graph bounds mapped into canvas-local coordinates (matches node placement).
  static Rect canvasBoundsFromPositions(Map<String, Offset> positions) {
    final graphBounds = computeBounds(positions);
    return Rect.fromLTWH(
      kGraphCanvasPadding,
      kGraphCanvasPadding,
      graphBounds.width,
      graphBounds.height,
    );
  }

  static Matrix4 fitTransform({
    required Map<String, Offset> positions,
    required Size viewportSize,
    double padding = kGraphCanvasPadding,
  }) {
    if (positions.isEmpty || viewportSize.isEmpty) {
      return Matrix4.identity();
    }
    final canvasBounds = canvasBoundsFromPositions(positions);
    final graphWidth = canvasBounds.width;
    final graphHeight = canvasBounds.height;
    if (graphWidth <= 0 || graphHeight <= 0) {
      return Matrix4.identity();
    }
    final scaleX = (viewportSize.width - padding * 2) / graphWidth;
    final scaleY = (viewportSize.height - padding * 2) / graphHeight;
    final scale = math.min(scaleX, scaleY).clamp(kGraphMinScale, kGraphMaxScale);
    final centerX = canvasBounds.left + graphWidth / 2;
    final centerY = canvasBounds.top + graphHeight / 2;

    return Matrix4.identity()
      ..translate(viewportSize.width / 2, viewportSize.height / 2)
      ..scale(scale)
      ..translate(-centerX, -centerY);
  }

  /// Transforms canvas-local bounds into viewport coordinates after fit.
  static Rect viewportBoundsAfterFit({
    required Map<String, Offset> positions,
    required Size viewportSize,
    double padding = kGraphCanvasPadding,
  }) {
    final transform = fitTransform(
      positions: positions,
      viewportSize: viewportSize,
      padding: padding,
    );
    final canvasBounds = canvasBoundsFromPositions(positions);
    final topLeft = MatrixUtils.transformPoint(transform, canvasBounds.topLeft);
    final bottomRight = MatrixUtils.transformPoint(transform, canvasBounds.bottomRight);
    return Rect.fromPoints(topLeft, bottomRight);
  }

  /// Border intersection points for a line between two node centers.
  static ({Offset start, Offset end}) computeEdgeEndpoints({
    required Offset sourceCenter,
    required Offset targetCenter,
    double nodeWidth = kGraphNodeWidth,
    double nodeHeight = kGraphNodeHeight,
  }) {
    return (
      start: _borderPoint(sourceCenter, targetCenter, nodeWidth, nodeHeight),
      end: _borderPoint(targetCenter, sourceCenter, nodeWidth, nodeHeight),
    );
  }

  static Offset _borderPoint(
    Offset center,
    Offset toward,
    double width,
    double height,
  ) {
    final dx = toward.dx - center.dx;
    final dy = toward.dy - center.dy;
    if (dx == 0 && dy == 0) {
      return center;
    }
    final halfW = width / 2;
    final halfH = height / 2;
    final scaleX = dx.abs() > 0 ? halfW / dx.abs() : double.infinity;
    final scaleY = dy.abs() > 0 ? halfH / dy.abs() : double.infinity;
    final scale = math.min(scaleX, scaleY);
    return Offset(center.dx + dx * scale, center.dy + dy * scale);
  }
}