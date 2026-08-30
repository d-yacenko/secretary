import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:personal_secretary/api/api_models.dart';
import 'package:personal_secretary/graph/graph_layout.dart';
import 'package:personal_secretary/ui/domain_labels.dart';

SecretaryObject _task({
  required String id,
  required String title,
  String status = 'В работе',
}) {
  return SecretaryObject(
    id: id,
    kind: 'task',
    title: title,
    metadata: {},
    origin: 'user',
    state: 'confirmed',
    status: status,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
  );
}

Widget _nodeCard(SecretaryObject object) {
  return MaterialApp(
    locale: const Locale('ru', 'RU'),
    localizationsDelegates: const [
      GlobalMaterialLocalizations.delegate,
      GlobalWidgetsLocalizations.delegate,
      GlobalCupertinoLocalizations.delegate,
    ],
    supportedLocales: const [Locale('ru', 'RU')],
    home: Scaffold(
      body: Center(
        child: Material(
          child: SizedBox(
            width: kGraphNodeWidth,
            height: kGraphNodeHeight,
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.task_alt_outlined, size: 14),
                      const SizedBox(width: 4),
                      Expanded(
                        child: Text(
                          objectKindLabel(object.kind),
                          style: const TextStyle(fontSize: 11),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                  Text(
                    object.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 12),
                  ),
                  Text(
                    objectLifecycleDisplayLabel(object),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 11),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

void main() {
  final sizes = <Size>[
    const Size(320, 640),
    const Size(360, 800),
    const Size(393, 852),
    const Size(1280, 800),
  ];

  for (final size in sizes) {
    testWidgets('graph node no overflow at ${size.width}x${size.height}', (tester) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final object = _task(
        id: 'task-1',
        title: 'Подготовить презентацию для важного совещания',
      );

      await tester.pumpWidget(_nodeCard(object));
      await tester.pump();
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('graph node no overflow with enlarged text', (tester) async {
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final object = _task(
      id: 'task-2',
      title: 'Очень длинное название задачи на русском языке',
      status: 'open',
    );

    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(1.25)),
        child: _nodeCard(object),
      ),
    );
    await tester.pump();
    expect(tester.takeException(), isNull);
  });
}
