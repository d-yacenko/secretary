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
    required String? rootId,
    required Map<String, Offset> existing,
    bool freshRoot = false,
  }) {
    final positions = freshRoot ? <String, Offset>{} : Map<String, Offset>.from(existing);
    final sorted = List<SecretaryObject>.from(nodes);
    sorted.sort((a, b) {
      final left = '${a.kind}|${a.title}|${a.id}';
      final right = '${b.kind}|${b.title}|${b.id}';
      return left.compareTo(right);
    });

    if (rootId != null) {
      if (!positions.containsKey(rootId)) {
        positions[rootId] = const Offset(0, 0);
      }
      final ringNodes = sorted.where((node) => node.id != rootId).toList();
      final newcomers = ringNodes.where((node) => !positions.containsKey(node.id)).toList();
      if (newcomers.isNotEmpty) {
        final rootTopLeft = positions[rootId]!;
        final rootCenter = Offset(
          rootTopLeft.dx + kGraphNodeWidth / 2,
          rootTopLeft.dy + kGraphNodeHeight / 2,
        );
        final radius = _ringRadiusForCount(newcomers.length);
        final step = (2 * math.pi) / newcomers.length;
        for (var index = 0; index < newcomers.length; index++) {
          final angle = step * index - math.pi / 2;
          final ringCenter = Offset(
            rootCenter.dx + math.cos(angle) * radius,
            rootCenter.dy + math.sin(angle) * radius,
          );
          positions[newcomers[index].id] = Offset(
            ringCenter.dx - kGraphNodeWidth / 2,
            ringCenter.dy - kGraphNodeHeight / 2,
          );
        }
      }
      return positions;
    }

    final newcomers = sorted.where((node) => !positions.containsKey(node.id)).toList();
    var column = 0;
    var row = 0;
    final originX = -(overviewColumnStep * (kGraphOverviewColumns - 1)) / 2;
    final originY = -overviewRowStep;
    for (final node in newcomers) {
      positions[node.id] = Offset(
        originX + column * overviewColumnStep,
        originY + row * overviewRowStep,
      );
      column += 1;
      if (column >= kGraphOverviewColumns) {
        column = 0;
        row += 1;
      }
    }
    return positions;
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