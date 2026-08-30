import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/api/api_models.dart';

void main() {
  test('set task status proposal label', () {
    final action = PendingAction(
      toolName: 'set_task_status',
      arguments: {'object_id': 'id-1', 'status': 'done'},
    );
    expect(action.displayLabel, 'Set task status: done');
  });

  test('delete task proposal label', () {
    final action = PendingAction(
      toolName: 'delete_task',
      arguments: {'object_id': 'id-1'},
    );
    expect(action.displayLabel, 'Delete task');
  });

  test('affected object prefers lifecycle status in chip label', () {
    final affected = AssistantAffectedObject(
      objectId: 'id-1',
      title: 'Prepare report',
      kind: 'task',
      state: 'confirmed',
      status: 'done',
    );
    expect(affected.displayLabel, 'task: Prepare report — done');
  });

  test('affected object deleted status chip', () {
    final affected = AssistantAffectedObject(
      objectId: 'id-2',
      title: 'TEST-DELETE',
      kind: 'task',
      state: 'confirmed',
      status: 'deleted',
    );
    expect(affected.displayLabel, 'task: TEST-DELETE — deleted');
  });
}
