import 'package:flutter/material.dart';

void main() {
  runApp(const PersonalSecretaryApp());
}

class PersonalSecretaryApp extends StatelessWidget {
  const PersonalSecretaryApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Personal Secretary',
      home: Scaffold(
        appBar: AppBar(title: const Text('Personal Secretary')),
        body: const Center(child: Text('Personal Secretary OS')),
      ),
    );
  }
}
