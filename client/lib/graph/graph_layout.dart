import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter/material.dart';

import '../api/api_models.dart';

const double kGraphNodeWidth = 132;
const double kGraphNodeHeight = 68;
const double kGraphCanvasPadding = 80;

class GraphLayout {
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
      final center = positions[rootId]!;
      final ringNodes = sorted.where((node) => node.id != rootId).toList();
      final newcomers = ringNodes.where((node) => !positions.containsKey(node.id)).toList();
      if (newcomers.isNotEmpty) {
        final step = (2 * math.pi) / newcomers.length;
        final radius = 180.0;
        for (var index = 0; index < newcomers.length; index++) {
          final angle = step * index - math.pi / 2;
          positions[newcomers[index].id] = Offset(
            center.dx + math.cos(angle) * radius,
            center.dy + math.sin(angle) * radius,
          );
        }
      }
      return positions;
    }

    final newcomers = sorted.where((node) => !positions.containsKey(node.id)).toList();
    var column = 0;
    var row = 0;
    for (final node in newcomers) {
      positions[node.id] = Offset(column * 160 - 240, row * 110 - 120);
      column += 1;
      if (column >= 4) {
        column = 0;
        row += 1;
      }
    }
    return positions;
  }

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

  static Matrix4 fitTransform({
    required Map<String, Offset> positions,
    required Size viewportSize,
    double padding = kGraphCanvasPadding,
  }) {
    if (positions.isEmpty || viewportSize.isEmpty) {
      return Matrix4.identity();
    }
    final bounds = computeBounds(positions);
    final graphWidth = bounds.width;
    final graphHeight = bounds.height;
    if (graphWidth <= 0 || graphHeight <= 0) {
      return Matrix4.identity();
    }
    final scaleX = (viewportSize.width - padding * 2) / graphWidth;
    final scaleY = (viewportSize.height - padding * 2) / graphHeight;
    final scale = math.min(math.min(scaleX, scaleY), 1.5);
    final centerX = bounds.left + graphWidth / 2;
    final centerY = bounds.top + graphHeight / 2;

    return Matrix4.identity()
      ..translate(viewportSize.width / 2, viewportSize.height / 2)
      ..scale(scale)
      ..translate(-centerX, -centerY);
  }
}

IconData iconForKind(String kind) {
  switch (kind) {
    case 'task':
      return Icons.task_alt_outlined;
    case 'email':
      return Icons.email_outlined;
    case 'event':
      return Icons.event_outlined;
    case 'file':
      return Icons.insert_drive_file_outlined;
    case 'note':
      return Icons.sticky_note_2_outlined;
    case 'chat':
    case 'message':
      return Icons.chat_bubble_outline;
    default:
      return Icons.category_outlined;
  }
}
