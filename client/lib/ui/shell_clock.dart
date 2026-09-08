import 'dart:async';

import 'package:flutter/material.dart';

import 'date_format.dart';

class ShellClock extends StatefulWidget {
  const ShellClock({
    super.key,
    this.now,
    this.tick = const Duration(minutes: 1),
  });

  final DateTime Function()? now;
  final Duration tick;

  @override
  State<ShellClock> createState() => _ShellClockState();
}

class _ShellClockState extends State<ShellClock> {
  late DateTime _now;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _now = (widget.now ?? DateTime.now)().toLocal();
    _timer = Timer.periodic(widget.tick, (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _now = (widget.now ?? DateTime.now)().toLocal();
      });
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              formatRussianClockTime(_now),
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          const SizedBox(height: 4),
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              formatRussianDayMonth(_now),
              textAlign: TextAlign.center,
              style: theme.textTheme.bodySmall,
            ),
          ),
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              formatRussianWeekday(_now),
              textAlign: TextAlign.center,
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
