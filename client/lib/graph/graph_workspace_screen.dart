import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../api/api_models.dart';
import '../api/secretary_api_client.dart';
import '../assistant/assistant_controller.dart';
import '../auth/auth_controller.dart';
import '../capture/capture_controller.dart';
import '../navigation/secretary_navigation.dart';
import '../tasks/task_management_actions.dart';
import '../ui/domain_labels.dart';
import '../ui/object_dates.dart';
import '../ui/object_visuals.dart';
import 'graph_layout.dart';
import 'graph_workspace_controller.dart';

class GraphWorkspaceScreen extends StatefulWidget {
  const GraphWorkspaceScreen({
    super.key,
    required this.controller,
    required this.apiClient,
    required this.authController,
    required this.captureController,
    required this.assistantController,
    required this.onAskSecretary,
  });

  final GraphWorkspaceController controller;
  final SecretaryApiClient apiClient;
  final AuthController authController;
  final CaptureController captureController;
  final AssistantController assistantController;
  final void Function(SecretaryObject object) onAskSecretary;

  @override
  State<GraphWorkspaceScreen> createState() => _GraphWorkspaceScreenState();
}

class _GraphWorkspaceScreenState extends State<GraphWorkspaceScreen> {
  final TransformationController _transform = TransformationController();
  final TextEditingController _searchController = TextEditingController();
  List<SecretaryObject> _searchResults = [];
  bool _searching = false;
  Size? _canvasViewportSize;

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onControllerChanged);
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onControllerChanged);
    _searchController.dispose();
    _transform.dispose();
    super.dispose();
  }

  void _onControllerChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  Future<void> _runSearch(String query, String? kind) async {
    if (query.trim().isEmpty) {
      setState(() {
        _searchResults = [];
        _searching = false;
      });
      await widget.controller.loadOverview();
      return;
    }
    setState(() => _searching = true);
    try {
      final results = await widget.apiClient.searchObjects(
        query: query.trim(),
        kind: kind,
      );
      setState(() {
        _searchResults = results;
        _searching = false;
      });
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } catch (_) {
      setState(() => _searching = false);
    }
  }

  void _fitView() {
    final viewportSize = _canvasViewportSize;
    if (viewportSize == null || viewportSize.isEmpty) {
      return;
    }
    _transform.value = GraphLayout.fitTransform(
      positions: widget.controller.positions,
      viewportSize: viewportSize,
    );
  }

  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.sizeOf(context).width >= 900;
    final canvas = _buildCanvas(context);
    final details = _buildDetailPanel(context, compact: !isWide);

    return Column(
      children: [
        _buildToolbar(context),
        if (widget.controller.errorMessage != null &&
            widget.controller.loadState == GraphWorkspaceLoadState.ready)
          Material(
            color: Theme.of(context).colorScheme.errorContainer,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Text(widget.controller.errorMessage!),
            ),
          ),
        if (widget.controller.truncated)
          Material(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Text(
                'Некоторые связанные объекты скрыты лимитом рабочей области.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ),
        Expanded(
          child: isWide
              ? Row(
                  children: [
                    Expanded(child: canvas),
                    SizedBox(width: 360, child: details),
                  ],
                )
              : Stack(
                  children: [
                    Positioned.fill(child: canvas),
                    if (widget.controller.selectedObject != null)
                      Positioned(
                        left: 0,
                        right: 0,
                        bottom: 0,
                        child: Material(
                          elevation: 4,
                          child: ConstrainedBox(
                            constraints: BoxConstraints(
                              maxHeight: MediaQuery.sizeOf(context).height * 0.45,
                            ),
                            child: details,
                          ),
                        ),
                      ),
                  ],
                ),
        ),
      ],
    );
  }

  Widget _buildToolbar(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          SizedBox(
            width: 220,
            child: TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Поиск по графу',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searching
                    ? const Padding(
                        padding: EdgeInsets.all(12),
                        child: SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                      )
                    : null,
                isDense: true,
              ),
              onSubmitted: (value) => _runSearch(value, widget.controller.searchKindFilter),
            ),
          ),
          DropdownButton<String?>(
            value: widget.controller.searchKindFilter,
            hint: const Text('Все объекты'),
            items: const [
              DropdownMenuItem(value: null, child: Text('Все объекты')),
              DropdownMenuItem(value: 'task', child: Text('Задачи')),
            ],
            onChanged: (value) {
              widget.controller.searchKindFilter = value;
              _runSearch(_searchController.text, value);
            },
          ),
          if (_searchResults.isNotEmpty)
            SizedBox(
              height: 40,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: _searchResults.length,
                separatorBuilder: (_, __) => const SizedBox(width: 8),
                itemBuilder: (context, index) {
                  final object = _searchResults[index];
                  return ActionChip(
                    label: Text(object.title, overflow: TextOverflow.ellipsis),
                    onPressed: () => widget.controller.reRoot(object.id),
                  );
                },
              ),
            ),
          Tooltip(
            message: 'К обзору',
            child: IconButton(
              onPressed: widget.controller.loadOverview,
              icon: const Icon(Icons.grid_view_outlined),
            ),
          ),
          Tooltip(
            message: 'Уместить граф',
            child: IconButton(
              onPressed: _fitView,
              icon: const Icon(Icons.fit_screen_outlined),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCanvas(BuildContext context) {
    if (widget.controller.loadState == GraphWorkspaceLoadState.loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (widget.controller.loadState == GraphWorkspaceLoadState.error) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(widget.controller.errorMessage ?? 'Не удалось загрузить граф'),
            const SizedBox(height: 8),
            FilledButton(
              onPressed: widget.controller.loadOverview,
              child: const Text('Повторить'),
            ),
          ],
        ),
      );
    }

    final nodes = widget.controller.nodes;
    final edges = widget.controller.edges;
    final positions = widget.controller.positions;
    final bounds = GraphLayout.computeBounds(positions);
    final canvasWidth = bounds.width + kGraphCanvasPadding * 2;
    final canvasHeight = bounds.height + kGraphCanvasPadding * 2;
    final selectedObjectId = widget.controller.selectedObjectId;
    final focusMode = selectedObjectId != null;
    final focusNeighborIds = _focusNeighborIds(edges, selectedObjectId);

    return LayoutBuilder(
      builder: (context, constraints) {
        final viewportSize = Size(constraints.maxWidth, constraints.maxHeight);
        if (_canvasViewportSize != viewportSize) {
          _canvasViewportSize = viewportSize;
        }
        if (widget.controller.shouldFitAfterLayout) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (!mounted) {
              return;
            }
            _transform.value = GraphLayout.fitTransform(
              positions: positions,
              viewportSize: viewportSize,
            );
            widget.controller.clearFitRequest();
          });
        }
        return InteractiveViewer(
          constrained: false,
          transformationController: _transform,
          minScale: kGraphMinScale,
          maxScale: kGraphMaxScale,
          boundaryMargin: const EdgeInsets.all(200),
          child: SizedBox(
            width: canvasWidth,
            height: canvasHeight,
            child: Stack(
              clipBehavior: Clip.none,
              children: [
                CustomPaint(
                  size: Size(canvasWidth, canvasHeight),
                  painter: _GraphEdgePainter(
                    edges: edges,
                    positions: positions,
                    bounds: bounds,
                    padding: kGraphCanvasPadding,
                    selectedEdgeId: widget.controller.selectedEdgeId,
                    selectedObjectId: selectedObjectId,
                    focusMode: focusMode,
                    colorScheme: Theme.of(context).colorScheme,
                  ),
                ),
                ...nodes.map((node) {
                  final position = positions[node.id] ?? const Offset(0, 0);
                  final selected = selectedObjectId == node.id;
                  final emphasized = !focusMode ||
                      selected ||
                      focusNeighborIds.contains(node.id);
                  return Positioned(
                    left: position.dx - bounds.left + kGraphCanvasPadding,
                    top: position.dy - bounds.top + kGraphCanvasPadding,
                    child: _GraphNodeCard(
                      object: node,
                      selected: selected,
                      focusDimmed: focusMode && !emphasized,
                      onTap: () => widget.controller.selectObject(node.id),
                    ),
                  );
                }),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildDetailPanel(BuildContext context, {required bool compact}) {
    final object = widget.controller.selectedObject;
    if (object == null) {
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Text(
          'Выберите объект для просмотра.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      );
    }

    final relatedEdges = widget.controller.edges.where(
      (edge) => edge.sourceId == object.id || edge.targetId == object.id,
    );

    final primaryDate = objectPrimaryDateLabel(object);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            Icon(iconForKind(object.kind)),
            const SizedBox(width: 8),
            if (object.provider != null) ...[
              providerBadge(context, object.provider!),
              const SizedBox(width: 8),
            ],
            Expanded(
              child: Text(object.title, style: Theme.of(context).textTheme.titleMedium),
            ),
            if (object.kind == 'task' && !object.isDeletedTask)
              IconButton(
                tooltip: 'Удалить задачу',
                onPressed: () => _deleteTask(context, object),
                icon: Icon(
                  Icons.delete_outline,
                  color: Theme.of(context).colorScheme.error,
                ),
              ),
            IconButton(
              tooltip: 'Закрыть',
              onPressed: () => widget.controller.selectObject(null),
              icon: const Icon(Icons.close),
            ),
          ],
        ),
        SelectionArea(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(objectSummaryLabel(object)),
              if (object.body != null) ...[
                const SizedBox(height: 8),
                Text(object.body!),
              ],
              if (primaryDate.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    object.kind == 'task'
                        ? 'Срок: $primaryDate'
                        : 'Дата: $primaryDate',
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            Tooltip(
              message: 'Спросить секретаря',
              child: OutlinedButton.icon(
                onPressed: () {
                  widget.assistantController.setObjectContext(object);
                  widget.onAskSecretary(object);
                },
                icon: const Icon(Icons.support_agent_outlined, size: 18),
                label: const Text('Спросить секретаря'),
              ),
            ),
            Tooltip(
              message: 'Использовать как контекст',
              child: OutlinedButton.icon(
                onPressed: () {
                  widget.captureController.attachObjectContext(object);
                  openCapture(context, captureController: widget.captureController);
                },
                icon: const Icon(Icons.add_task_outlined, size: 18),
                label: Text(compact ? 'Контекст' : 'Использовать как контекст'),
              ),
            ),
            Tooltip(
              message: 'Открыть подробности',
              child: OutlinedButton.icon(
                onPressed: () async {
                  final controller = widget.controller;
                  await openObjectDetail(
                    context,
                    objectId: object.id,
                    apiClient: widget.apiClient,
                    authController: widget.authController,
                    captureController: widget.captureController,
                    assistantController: widget.assistantController,
                    onAskSecretary: widget.onAskSecretary,
                    onShowInGraph: (id) => controller.reRoot(id),
                    onTaskUpdated: controller.applyTaskMutation,
                  );
                  if (!mounted) {
                    return;
                  }
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    if (!mounted) {
                      return;
                    }
                    controller.refreshCurrentWorkspace();
                  });
                },
                icon: const Icon(Icons.open_in_new, size: 18),
                label: const Text('Подробнее'),
              ),
            ),
            Tooltip(
              message: 'Показать связи',
              child: OutlinedButton.icon(
                onPressed: widget.controller.expandSelected,
                icon: const Icon(Icons.hub_outlined, size: 18),
                label: const Text('Показать связи'),
              ),
            ),
            Tooltip(
              message: 'В центр',
              child: OutlinedButton.icon(
                onPressed: () => widget.controller.reRoot(object.id),
                icon: const Icon(Icons.center_focus_strong_outlined, size: 18),
                label: const Text('В центр'),
              ),
            ),
            Tooltip(
              message: 'Добавить связь',
              child: OutlinedButton.icon(
                onPressed: () => _addRelation(context, object),
                icon: const Icon(Icons.link, size: 18),
                label: const Text('Добавить связь'),
              ),
            ),
          ],
        ),
        TaskManagementActions(
          task: object,
          apiClient: widget.apiClient,
          authController: widget.authController,
          compact: compact,
          onTaskUpdated: widget.controller.applyTaskMutation,
        ),
        const SizedBox(height: 12),
        _DetailSectionHeader(title: 'Связи'),
        ...relatedEdges.map((edge) {
          final otherId = edge.sourceId == object.id ? edge.targetId : edge.sourceId;
          final other = widget.controller.nodeById(otherId);
          return ListTile(
            dense: true,
            selected: widget.controller.selectedEdgeId == edge.id,
            onTap: () {
              widget.controller.selectEdge(edge.id);
              if (other != null) {
                widget.controller.selectObject(other.id);
              }
            },
            title: Text(relationTypeLabel(edge.type)),
            subtitle: Text(other?.title ?? otherId),
            trailing: edge.origin == 'user'
                ? IconButton(
                    tooltip: 'Удалить связь',
                    icon: const Icon(Icons.link_off_outlined),
                    onPressed: () => _removeRelation(context, edge),
                  )
                : null,
          );
        }),
      ],
    );
  }

  Future<void> _addRelation(BuildContext context, SecretaryObject source) async {
    String relationType = 'related_to';
    SecretaryObject? target;
    final queryController = TextEditingController();
    List<SecretaryObject> options = [];

    await showDialog<void>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              title: const Text('Добавить связь'),
              content: SizedBox(
                width: 360,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    DropdownButtonFormField<String>(
                      value: relationType,
                      items: const [
                        DropdownMenuItem(value: 'related_to', child: Text('Связано с')),
                        DropdownMenuItem(value: 'references', child: Text('Ссылается на')),
                        DropdownMenuItem(value: 'depends_on', child: Text('Зависит от')),
                      ],
                      onChanged: (value) {
                        if (value != null) {
                          setState(() => relationType = value);
                        }
                      },
                    ),
                    TextField(
                      controller: queryController,
                      decoration: const InputDecoration(labelText: 'Поиск объекта'),
                      onSubmitted: (value) async {
                        final results = await widget.apiClient.searchObjects(query: value);
                        setState(() => options = results);
                      },
                    ),
                    ...options.map(
                      (item) => ListTile(
                        title: Text(item.title),
                        subtitle: Text(objectKindLabel(item.kind)),
                        selected: target?.id == item.id,
                        onTap: () => setState(() => target = item),
                      ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Отмена'),
                ),
                FilledButton(
                  onPressed: target == null ? null : () => Navigator.pop(context),
                  child: const Text('Создать'),
                ),
              ],
            );
          },
        );
      },
    );

    if (target == null || target!.id == source.id) {
      return;
    }
    try {
      final response = await widget.apiClient.createRelation(
        sourceId: source.id,
        targetId: target!.id,
        type: relationType,
      );
      await widget.controller.mergeRelationContext(
        source.id,
        target: target,
        edge: response.edge,
      );
    } on ApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    }
  }

  Set<String> _focusNeighborIds(List<SecretaryEdge> edges, String? selectedId) {
    if (selectedId == null) {
      return {};
    }
    final neighbors = <String>{};
    for (final edge in edges) {
      if (edge.sourceId == selectedId) {
        neighbors.add(edge.targetId);
      }
      if (edge.targetId == selectedId) {
        neighbors.add(edge.sourceId);
      }
    }
    return neighbors;
  }

  Future<void> _deleteTask(BuildContext context, SecretaryObject task) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Удалить задачу?'),
        content: Text(
          '${task.title}\n\nЗадача будет скрыта из обычного поиска и активных представлений. '
          'История в графе и связи сохранятся.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Отмена'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Удалить'),
          ),
        ],
      ),
    );
    if (confirmed != true) {
      return;
    }
    try {
      final response = await widget.apiClient.softDeleteTask(task.id);
      await widget.controller.applyTaskMutation(response.object);
    } on AuthenticationException {
      widget.authController.handleAuthenticationFailure();
    } on ApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    }
  }

  Future<void> _removeRelation(BuildContext context, SecretaryEdge edge) async {
    final source = widget.controller.nodeById(edge.sourceId);
    final target = widget.controller.nodeById(edge.targetId);
    final sourceTitle = source?.title ?? edge.sourceId;
    final targetTitle = target?.title ?? edge.targetId;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Удалить связь?'),
        content: Text(
          '$sourceTitle —${relationTypeLabel(edge.type)}→ $targetTitle',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Отмена'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Удалить'),
          ),
        ],
      ),
    );
    if (confirmed != true) {
      return;
    }
    try {
      await widget.apiClient.deleteRelation(edge.id);
      widget.controller.removeEdge(edge.id);
    } on ApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    }
  }
}

String _graphNodeFooterLabel(SecretaryObject object) {
  if (object.kind == 'task') {
    final lifecycle = objectLifecycleDisplayLabel(object);
    final due = objectPrimaryDateLabel(object);
    if (due.isNotEmpty) {
      return '$lifecycle • $due';
    }
    return lifecycle;
  }
  final primaryDate = objectPrimaryDateLabel(object);
  if (primaryDate.isNotEmpty) {
    return primaryDate;
  }
  return objectLifecycleDisplayLabel(object);
}

class _DetailSectionHeader extends StatelessWidget {
  const _DetailSectionHeader({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: theme.textTheme.labelLarge?.copyWith(
              color: theme.colorScheme.primary,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 4),
          Divider(height: 1, color: theme.colorScheme.outlineVariant),
        ],
      ),
    );
  }
}

class _GraphNodeCard extends StatelessWidget {
  const _GraphNodeCard({
    required this.object,
    required this.selected,
    required this.focusDimmed,
    required this.onTap,
  });

  final SecretaryObject object;
  final bool selected;
  final bool focusDimmed;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final baseColor = selected
        ? scheme.primaryContainer
        : object.kind == 'task'
            ? scheme.surfaceContainerHigh
            : scheme.surface;

    final card = Material(
      elevation: selected ? 4 : 1,
      color: baseColor,
      borderRadius: BorderRadius.circular(10),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(10),
        child: Container(
          width: kGraphNodeWidth,
          height: kGraphNodeHeight,
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: selected ? scheme.primary : scheme.outlineVariant,
              width: selected ? 2 : 1,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(iconForKind(object.kind), size: 16),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      objectKindLabel(object.kind),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.labelSmall,
                    ),
                  ),
                  if (object.provider != null)
                    providerBadge(context, object.provider!),
                ],
              ),
              const SizedBox(height: 4),
              Expanded(
                child: Text(
                  object.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
              ),
              Text(
                _graphNodeFooterLabel(object),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
              ),
            ],
          ),
        ),
      ),
    );

    return Opacity(
      opacity: focusDimmed ? 0.35 : 1,
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        child: card,
      ),
    );
  }
}

class _GraphEdgePainter extends CustomPainter {
  _GraphEdgePainter({
    required this.edges,
    required this.positions,
    required this.bounds,
    required this.padding,
    required this.selectedEdgeId,
    required this.selectedObjectId,
    required this.focusMode,
    required this.colorScheme,
  });

  final List<SecretaryEdge> edges;
  final Map<String, Offset> positions;
  final Rect bounds;
  final double padding;
  final String? selectedEdgeId;
  final String? selectedObjectId;
  final bool focusMode;
  final ColorScheme colorScheme;

  Offset _nodeCenter(String objectId) {
    final position = positions[objectId] ?? const Offset(0, 0);
    return Offset(
      position.dx - bounds.left + padding + kGraphNodeWidth / 2,
      position.dy - bounds.top + padding + kGraphNodeHeight / 2,
    );
  }

  bool _isFocusEdge(SecretaryEdge edge) {
    if (selectedObjectId == null) {
      return false;
    }
    return edge.sourceId == selectedObjectId || edge.targetId == selectedObjectId;
  }

  @override
  void paint(Canvas canvas, Size size) {
    for (final edge in edges) {
      if (!positions.containsKey(edge.sourceId) ||
          !positions.containsKey(edge.targetId)) {
        continue;
      }

      final focusEdge = focusMode && _isFocusEdge(edge);
      final dimmed = focusMode && !focusEdge;
      final emphasized = edge.id == selectedEdgeId || focusEdge;

      var paint = Paint()
        ..strokeWidth = emphasized ? 2.5 : 1.5
        ..color = edge.state == 'proposed'
            ? colorScheme.tertiary
            : emphasized
                ? colorScheme.primary
                : colorScheme.outline
        ..style = PaintingStyle.stroke;

      if (dimmed) {
        paint = paint..color = paint.color.withValues(alpha: 0.35);
      }

      final sourceCenter = _nodeCenter(edge.sourceId);
      final targetCenter = _nodeCenter(edge.targetId);
      final endpoints = GraphLayout.computeEdgeEndpoints(
        sourceCenter: sourceCenter,
        targetCenter: targetCenter,
      );
      final start = endpoints.start;
      final end = endpoints.end;
      canvas.drawLine(start, end, paint);

      final angle = math.atan2(end.dy - start.dy, end.dx - start.dx);
      const arrow = 10.0;
      final tip = end;
      final left = Offset(
        tip.dx - arrow * math.cos(angle - 0.4),
        tip.dy - arrow * math.sin(angle - 0.4),
      );
      final right = Offset(
        tip.dx - arrow * math.cos(angle + 0.4),
        tip.dy - arrow * math.sin(angle + 0.4),
      );
      final path = Path()
        ..moveTo(tip.dx, tip.dy)
        ..lineTo(left.dx, left.dy)
        ..lineTo(right.dx, right.dy)
        ..close();
      canvas.drawPath(path, paint);
    }
  }

  @override
  bool shouldRepaint(covariant _GraphEdgePainter oldDelegate) => true;
}
