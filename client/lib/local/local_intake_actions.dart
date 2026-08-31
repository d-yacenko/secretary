import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../assistant/assistant_controller.dart';
import 'local_file_intake_service.dart';

typedef IntakeObjectHandler = void Function(SecretaryObject object);

class LocalIntakeActions {
  LocalIntakeActions({
    required this.apiClient,
    required this.authController,
    this.captureController,
    this.assistantController,
    this.onIntakeObject,
  })  : _intakeService = LocalFileIntakeService(apiClient: apiClient);

  final SecretaryApiClient apiClient;
  final AuthController authController;
  final CaptureController? captureController;
  final AssistantController? assistantController;
  final IntakeObjectHandler? onIntakeObject;

  final LocalFileIntakeService _intakeService;

  Future<void> pickAndRegisterFile(BuildContext context) async {
    if (kIsWeb) {
      _showMessage(context, 'Выбор файла недоступен в этой среде');
      return;
    }
    final result = await FilePicker.platform.pickFiles();
    if (result == null || result.files.isEmpty) {
      return;
    }
    final path = result.files.single.path;
    if (path == null) {
      _showMessage(context, 'Не удалось прочитать файл');
      return;
    }
    await _registerFiles(context, [File(path)]);
  }

  Future<void> pickAndRegisterFolder(BuildContext context) async {
    if (kIsWeb) {
      return;
    }
    final path = await FilePicker.platform.getDirectoryPath();
    if (path == null) {
      return;
    }
    final indexing = await _askFolderIndexingPolicy(context);
    if (indexing == null) {
      return;
    }
    await _registerFolder(context, Directory(path), indexSupported: indexing);
  }

  Future<void> registerDroppedFiles(
    BuildContext context,
    List<String> paths,
  ) async {
    if (paths.isEmpty) {
      return;
    }
    final bounded = paths.take(10).map((p) => File(p)).toList();
    await _registerFiles(context, bounded);
  }

  Future<void> _registerFiles(BuildContext context, List<File> files) async {
    for (final file in files) {
      try {
        final object = await _intakeService.registerFileAndFetch(file);
        onIntakeObject?.call(object);
        if (assistantController != null) {
          assistantController!.setObjectContext(object);
        }
        _showMessage(
          context,
          object.metadata['indexing_policy'] == 'metadata_only'
              ? 'Формат пока индексируется только по метаданным: ${object.title}'
              : 'Файл добавлен: ${object.title}',
        );
      } on AuthenticationException {
        authController.handleAuthenticationFailure();
        return;
      } on ApiException catch (e) {
        _showMessage(context, e.message);
      } catch (_) {
        _showMessage(context, 'Не удалось зарегистрировать источник');
      }
    }
  }

  Future<void> _registerFolder(
    BuildContext context,
    Directory root, {
    required bool indexSupported,
  }) async {
    try {
      await _intakeService.registerFolder(root, indexSupported: indexSupported);
      _showMessage(context, 'Папка добавлена: ${root.path}');
    } on AuthenticationException {
      authController.handleAuthenticationFailure();
    } on ApiException catch (e) {
      _showMessage(context, e.message);
    } catch (_) {
      _showMessage(context, 'Не удалось зарегистрировать источник');
    }
  }

  Future<bool?> _askFolderIndexingPolicy(BuildContext context) async {
    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Добавить папку'),
        content: const Text('Как индексировать содержимое папки?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Только имена и метаданные'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Индексировать поддерживаемые файлы'),
          ),
        ],
      ),
    );
  }

  void _showMessage(BuildContext context, String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }
}

Widget buildAddFileButton({
  required LocalIntakeActions actions,
  required BuildContext context,
}) {
  return TextButton(
    key: const Key('add_local_file_button'),
    onPressed: () => actions.pickAndRegisterFile(context),
    child: const Text('Добавить файл'),
  );
}

Widget buildAddFolderButton({
  required LocalIntakeActions actions,
  required BuildContext context,
}) {
  return TextButton(
    key: const Key('add_local_folder_button'),
    onPressed: () => actions.pickAndRegisterFolder(context),
    child: const Text('Добавить папку'),
  );
}
