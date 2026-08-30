import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../api/api_models.dart';

const double kGraphNodeWidth = 132;
const double kGraphNodeHeight = 68;

class GraphLayout {
  static Map<String, Offset> computePositions({
    required List<SecretaryObject> nodes,
    required String? rootId,
    required Map<String, Offset> existing,
  }) {
    final positions = Map<String, Offset>.from(existing);
    final sorted = List<SecretaryObject>.from(nodes);
    sorted.sort((a, b) {
      final left = '${a.kind}|${a.title}|${a.id}';
      final right = '${b.kind}|${b.title}|${b.id}';
      return left.compareTo(right);
    });

    final newcomers = sorted.where((node) => !positions.containsKey(node.id)).toList();
    if (newcomers.isEmpty) {
      return positions;
    }

    if (rootId != null && positions.containsKey(rootId)) {
      final center = positions[rootId]!;
      final ringNodes = newcomers.where((node) => node.id != rootId).toList();
      if (ringNodes.isNotEmpty) {
        final step = (2 * math.pi) / ringNodes.length;
        final radius = 180.0;
        for (var index = 0; index < ringNodes.length; index++) {
          final angle = step * index - math.pi / 2;
          positions[ringNodes[index].id] = Offset(
            center.dx + math.cos(angle) * radius,
            center.dy + math.sin(angle) * radius,
          );
        }
      }
      if (!positions.containsKey(rootId)) {
        positions[rootId] = const Offset(0, 0);
      }
      return positions;
    }

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
