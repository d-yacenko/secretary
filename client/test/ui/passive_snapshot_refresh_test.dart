import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/ui/passive_snapshot_refresh.dart';

void main() {
  setUp(() {
    WidgetsFlutterBinding.ensureInitialized();
  });

  test('runs periodic callback on interval', () async {
    var count = 0;
    final refresh = PassiveSnapshotRefresh(
      interval: const Duration(milliseconds: 40),
      isPaused: () => false,
      onRefresh: () async {
        count++;
      },
    );
    refresh.attach();
    await Future<void>.delayed(const Duration(milliseconds: 120));
    refresh.dispose();
    expect(count, greaterThanOrEqualTo(2));
  });

  test('paused tick skips callback but polling survives', () async {
    var paused = true;
    var count = 0;
    final refresh = PassiveSnapshotRefresh(
      interval: const Duration(milliseconds: 40),
      isPaused: () => paused,
      onRefresh: () async {
        count++;
      },
    );
    refresh.attach();
    await Future<void>.delayed(const Duration(milliseconds: 60));
    expect(count, 0);

    paused = false;
    await Future<void>.delayed(const Duration(milliseconds: 80));
    refresh.dispose();
    expect(count, greaterThanOrEqualTo(1));
  });

  test('after unpause a later tick runs callback', () async {
    var paused = true;
    var count = 0;
    final refresh = PassiveSnapshotRefresh(
      interval: const Duration(milliseconds: 30),
      isPaused: () => paused,
      onRefresh: () async {
        count++;
      },
    );
    refresh.attach();
    await Future<void>.delayed(const Duration(milliseconds: 50));
    paused = false;
    await Future<void>.delayed(const Duration(milliseconds: 90));
    refresh.dispose();
    expect(count, greaterThanOrEqualTo(2));
  });

  test('does not run concurrent callbacks', () async {
    var inProgress = false;
    var overlaps = 0;
    final refresh = PassiveSnapshotRefresh(
      interval: const Duration(milliseconds: 20),
      isPaused: () => false,
      onRefresh: () async {
        if (inProgress) {
          overlaps++;
        }
        inProgress = true;
        await Future<void>.delayed(const Duration(milliseconds: 80));
        inProgress = false;
      },
    );
    refresh.attach();
    await Future<void>.delayed(const Duration(milliseconds: 200));
    refresh.dispose();
    expect(overlaps, 0);
  });

  test('lifecycle pause stops polling and resume restarts refresh', () async {
    var count = 0;
    final refresh = PassiveSnapshotRefresh(
      interval: const Duration(milliseconds: 40),
      isPaused: () => false,
      onRefresh: () async {
        count++;
      },
    );
    refresh.attach();
    await Future<void>.delayed(const Duration(milliseconds: 50));
    refresh.didChangeAppLifecycleState(AppLifecycleState.paused);
    final pausedCount = count;
    await Future<void>.delayed(const Duration(milliseconds: 80));
    expect(count, pausedCount);

    refresh.didChangeAppLifecycleState(AppLifecycleState.resumed);
    await Future<void>.delayed(const Duration(milliseconds: 80));
    refresh.dispose();
    expect(count, greaterThan(pausedCount));
  });

  test('dispose stops future callbacks', () async {
    var count = 0;
    final refresh = PassiveSnapshotRefresh(
      interval: const Duration(milliseconds: 30),
      isPaused: () => false,
      onRefresh: () async {
        count++;
      },
    );
    refresh.attach();
    await Future<void>.delayed(const Duration(milliseconds: 40));
    final beforeDispose = count;
    refresh.dispose();
    await Future<void>.delayed(const Duration(milliseconds: 80));
    expect(count, beforeDispose);
  });
}
