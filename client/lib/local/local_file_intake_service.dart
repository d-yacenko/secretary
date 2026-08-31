import 'dart:io';

import 'package:path/path.dart' as p;

import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import 'client_device_store.dart';
import 'local_resource_extractor.dart';

const _maxFolderDepth = 8;
const _maxFolderFiles = 200;
const _maxReportBatch = 100;

class LocalFileIntakeService {
  LocalFileIntakeService({
    required SecretaryApiClient apiClient,
    ClientDeviceStore? deviceStore,
    LocalResourceExtractor? extractor,
  })  : _apiClient = apiClient,
        _deviceStore = deviceStore ?? ClientDeviceStore(),
        _extractor = extractor ?? LocalResourceExtractor();

  final SecretaryApiClient _apiClient;
  final ClientDeviceStore _deviceStore;
  final LocalResourceExtractor _extractor;

  Future<ClientFileIntakeResult> registerFile(File file) async {
    final device = await _deviceStore.loadOrCreate();
    await _apiClient.registerLocalDevice(
      deviceKey: device.deviceKey,
      displayName: device.displayName,
    );
    final extraction = _extractor.extractFile(file);
    return _apiClient.clientFileIntake(
      deviceKey: device.deviceKey,
      sourcePath: extraction.sourcePath,
      filename: extraction.filename,
      size: extraction.size,
      modifiedAt: extraction.modifiedAt,
      contentRevision: extraction.contentRevision,
      representations: extraction.representations,
      contentHash: extraction.contentHash,
      metadataOnly: extraction.metadataOnly,
    );
  }

  Future<SecretaryObject> registerFileAndFetch(File file) async {
    final result = await registerFile(file);
    return _apiClient.getObject(result.objectId);
  }

  Future<void> registerFolder(
    Directory root, {
    required bool indexSupported,
  }) async {
    final device = await _deviceStore.loadOrCreate();
    await _apiClient.registerLocalDevice(
      deviceKey: device.deviceKey,
      displayName: device.displayName,
    );
    final rootPath = _normalizeRootPath(root.path);
    await _apiClient.registerLocalRoot(
      deviceKey: device.deviceKey,
      rootPath: rootPath,
      defaultPolicy: indexSupported ? 'index_text' : 'metadata_only',
    );

    final files = _boundedWalk(root);
    final metadataBatch = <Map<String, dynamic>>[];

    for (final file in files) {
      final relative = p.relative(file.path, from: root.path).replaceAll('\\', '/');
      final stat = file.statSync();
      final modifiedAt = stat.modified.toUtc().toIso8601String();
      final extension = p.extension(file.path).toLowerCase();
      final supported = _supportedSuffixes.contains(extension);

      if (indexSupported && supported) {
        final extraction = _extractor.extractFile(file);
        await _apiClient.clientFileIntake(
          deviceKey: device.deviceKey,
          sourcePath: relative,
          filename: p.basename(file.path),
          size: extraction.size,
          modifiedAt: extraction.modifiedAt,
          contentRevision: extraction.contentRevision,
          representations: extraction.representations,
          contentHash: extraction.contentHash,
          metadataOnly: extraction.metadataOnly,
          rootPath: rootPath,
          clientAbsolutePath: file.path,
        );
      } else {
        metadataBatch.add({
          'relative_path': relative,
          'size': stat.size,
          'modified_at': modifiedAt,
          'policy': 'metadata_only',
        });
      }
    }

    for (var i = 0; i < metadataBatch.length; i += _maxReportBatch) {
      final slice = metadataBatch.skip(i).take(_maxReportBatch).toList();
      if (slice.isEmpty) {
        continue;
      }
      await _apiClient.reportLocalFiles(
        deviceKey: device.deviceKey,
        rootPath: rootPath,
        files: slice,
      );
    }
  }

  List<File> _boundedWalk(Directory root) {
    final result = <File>[];
    void walk(Directory dir, int depth) {
      if (depth > _maxFolderDepth || result.length >= _maxFolderFiles) {
        return;
      }
      try {
        for (final entity in dir.listSync(followLinks: false)) {
          if (result.length >= _maxFolderFiles) {
            return;
          }
          if (entity is File) {
            result.add(entity);
          } else if (entity is Directory) {
            walk(entity, depth + 1);
          }
        }
      } catch (_) {
        // Skip unreadable directories.
      }
    }
    walk(root, 0);
    return result;
  }

  String _normalizeRootPath(String absolutePath) {
    return absolutePath.replaceAll('\\', '/').replaceFirst(RegExp('^/+'), '');
  }

  static const _supportedSuffixes = {'.txt', '.md', '.csv'};
}
