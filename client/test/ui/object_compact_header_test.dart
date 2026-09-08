import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/ui/object_presentation.dart';

void main() {
  Widget wrap(Widget child, {double width = 320}) {
    return MaterialApp(
      home: Scaffold(
        body: SizedBox(
          width: width,
          child: child,
        ),
      ),
    );
  }

  testWidgets('compact header places kind and provider before title', (tester) async {
    await tester.pumpWidget(
      wrap(
        ObjectCompactHeaderRow(
          title: 'Тема письма',
          kind: 'email',
          provider: 'gmail',
          trailingText: '09:42',
        ),
      ),
    );

    final iconBox = tester.getRect(find.byIcon(Icons.email_outlined));
    final providerBox = tester.getRect(find.byIcon(Icons.mail));
    final titleBox = tester.getRect(find.text('Тема письма'));
    final timeBox = tester.getRect(find.text('09:42'));

    expect(iconBox.left, lessThan(titleBox.left));
    expect(providerBox.left, lessThan(titleBox.left));
    expect(iconBox.left, lessThan(providerBox.left));
    expect(timeBox.left, greaterThan(titleBox.right));
  });

  testWidgets('compact header supports calendar event and missing provider', (tester) async {
    await tester.pumpWidget(
      wrap(
        Column(
          children: [
            ObjectCompactHeaderRow(
              title: 'Weekly sync',
              kind: 'event',
              provider: 'google_calendar',
              trailingText: '10:00',
            ),
            ObjectCompactHeaderRow(
              title: 'Локальная задача без провайдера',
              kind: 'task',
              provider: null,
              trailingText: 'сегодня',
            ),
          ],
        ),
      ),
    );

    expect(find.byIcon(Icons.event_outlined), findsOneWidget);
    expect(find.byIcon(Icons.calendar_month), findsOneWidget);
    expect(find.text('Weekly sync'), findsOneWidget);
    expect(find.text('Локальная задача без провайдера'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('compact header long russian title does not overflow on narrow width', (tester) async {
    await tester.pumpWidget(
      wrap(
        ObjectCompactHeaderRow(
          title: 'Очень длинное русское название письма которое должно сокращаться',
          kind: 'email',
          provider: 'yandex_mail',
          trailingText: 'вчера 18:30',
        ),
      ),
    );

    expect(tester.takeException(), isNull);
    expect(find.byIcon(Icons.alternate_email), findsOneWidget);
    expect(find.textContaining('вчера'), findsOneWidget);
  });
}
