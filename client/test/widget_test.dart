import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/main.dart';

void testAppLoads() {
  testWidgets('app loads', (tester) async {
    await tester.pumpWidget(const PersonalSecretaryApp());
    expect(find.text('Personal Secretary OS'), findsOneWidget);
  });
}
