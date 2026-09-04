class UserMe {
  UserMe(
      {required this.id, required this.displayName, required this.createdAt});

  final String id;
  final String displayName;
  final String createdAt;

  factory UserMe.fromJson(Map<String, dynamic> json) {
    return UserMe(
      id: json['id'] as String,
      displayName: json['display_name'] as String,
      createdAt: json['created_at'] as String,
    );
  }
}

class UserSettings {
  UserSettings({
    required this.timezone,
    required this.assistantModel,
    required this.assistantReasoningEffort,
    required this.assistantVerbosity,
    required this.openaiKeyConfigured,
    required this.allowedAssistantModels,
  });

  final String timezone;
  final String assistantModel;
  final String assistantReasoningEffort;
  final String assistantVerbosity;
  final bool openaiKeyConfigured;
  final List<String> allowedAssistantModels;

  factory UserSettings.fromJson(Map<String, dynamic> json) {
    return UserSettings(
      timezone: json['timezone'] as String,
      assistantModel: json['assistant_model'] as String,
      assistantReasoningEffort: json['assistant_reasoning_effort'] as String,
      assistantVerbosity: json['assistant_verbosity'] as String,
      openaiKeyConfigured: json['openai_key_configured'] as bool,
      allowedAssistantModels:
          (json['allowed_assistant_models'] as List<dynamic>)
              .map((item) => item as String)
              .toList(),
    );
  }
}

class UserIdentity {
  UserIdentity({
    required this.profileText,
    this.fullName,
    this.preferredName,
  });

  final String profileText;
  final String? fullName;
  final String? preferredName;

  factory UserIdentity.fromJson(Map<String, dynamic> json) {
    return UserIdentity(
      profileText: json['profile_text'] as String? ?? '',
      fullName: json['full_name'] as String?,
      preferredName: json['preferred_name'] as String?,
    );
  }
}

class GoogleConnection {
  GoogleConnection({
    required this.connected,
    this.email,
    required this.gmailAvailable,
    required this.calendarAvailable,
    required this.driveAvailable,
  });

  final bool connected;
  final String? email;
  final bool gmailAvailable;
  final bool calendarAvailable;
  final bool driveAvailable;

  factory GoogleConnection.fromJson(Map<String, dynamic> json) {
    return GoogleConnection(
      connected: json['connected'] as bool,
      email: json['email'] as String?,
      gmailAvailable: json['gmail_available'] as bool? ?? false,
      calendarAvailable: json['calendar_available'] as bool? ?? false,
      driveAvailable: json['drive_available'] as bool? ?? false,
    );
  }
}

class GoogleAuthorizationUrl {
  GoogleAuthorizationUrl({required this.authorizationUrl});

  final String authorizationUrl;

  factory GoogleAuthorizationUrl.fromJson(Map<String, dynamic> json) {
    return GoogleAuthorizationUrl(
      authorizationUrl: json['authorization_url'] as String,
    );
  }
}

class YandexMailConnection {
  YandexMailConnection({required this.connected, this.email});

  final bool connected;
  final String? email;

  factory YandexMailConnection.fromJson(Map<String, dynamic> json) {
    return YandexMailConnection(
      connected: json['connected'] as bool,
      email: json['email'] as String?,
    );
  }
}

class YandexCalendarConnection {
  YandexCalendarConnection({required this.connected, this.email});

  final bool connected;
  final String? email;

  factory YandexCalendarConnection.fromJson(Map<String, dynamic> json) {
    return YandexCalendarConnection(
      connected: json['connected'] as bool,
      email: json['email'] as String?,
    );
  }
}

class MattermostConnection {
  MattermostConnection({
    required this.accountId,
    required this.serverUrl,
    required this.remoteUserId,
    required this.username,
    this.displayName,
    this.email,
  });

  final String accountId;
  final String serverUrl;
  final String remoteUserId;
  final String username;
  final String? displayName;
  final String? email;

  factory MattermostConnection.fromJson(Map<String, dynamic> json) {
    return MattermostConnection(
      accountId: json['account_id'] as String,
      serverUrl: json['server_url'] as String,
      remoteUserId: json['remote_user_id'] as String,
      username: json['username'] as String,
      displayName: json['display_name'] as String?,
      email: json['email'] as String?,
    );
  }
}

class MattermostConnectResult {
  MattermostConnectResult({
    required this.status,
    required this.accountId,
    required this.serverUrl,
    required this.remoteUserId,
    required this.username,
    this.displayName,
    this.email,
  });

  final String status;
  final String accountId;
  final String serverUrl;
  final String remoteUserId;
  final String username;
  final String? displayName;
  final String? email;

  factory MattermostConnectResult.fromJson(Map<String, dynamic> json) {
    return MattermostConnectResult(
      status: json['status'] as String,
      accountId: json['account_id'] as String,
      serverUrl: json['server_url'] as String,
      remoteUserId: json['remote_user_id'] as String,
      username: json['username'] as String,
      displayName: json['display_name'] as String?,
      email: json['email'] as String?,
    );
  }
}

class YandexConnectResult {
  YandexConnectResult({
    required this.status,
    required this.accountId,
    required this.email,
  });

  final String status;
  final String accountId;
  final String email;

  factory YandexConnectResult.fromJson(Map<String, dynamic> json) {
    return YandexConnectResult(
      status: json['status'] as String,
      accountId: json['account_id'] as String,
      email: json['email'] as String,
    );
  }
}

class Connections {
  Connections({
    required this.google,
    required this.yandexMail,
    required this.yandexCalendar,
    required this.mattermost,
  });

  final GoogleConnection google;
  final YandexMailConnection yandexMail;
  final YandexCalendarConnection yandexCalendar;
  final List<MattermostConnection> mattermost;

  factory Connections.fromJson(Map<String, dynamic> json) {
    final mattermostRaw = json['mattermost'];
    return Connections(
      google: GoogleConnection.fromJson(json['google'] as Map<String, dynamic>),
      yandexMail: YandexMailConnection.fromJson(
          json['yandex_mail'] as Map<String, dynamic>),
      yandexCalendar: YandexCalendarConnection.fromJson(
        json['yandex_calendar'] as Map<String, dynamic>,
      ),
      mattermost: mattermostRaw is List<dynamic>
          ? mattermostRaw
              .map((e) =>
                  MattermostConnection.fromJson(e as Map<String, dynamic>))
              .toList()
          : const [],
    );
  }
}

class CaptureTaskRequest {
  CaptureTaskRequest({
    required this.text,
    this.title,
    this.contextObjectIds = const [],
    this.dependsOnIds = const [],
  });

  final String text;
  final String? title;
  final List<String> contextObjectIds;
  final List<String> dependsOnIds;

  Map<String, dynamic> toJson() {
    return {
      'text': text,
      if (title != null) 'title': title,
      'context_object_ids': contextObjectIds,
      'depends_on_ids': dependsOnIds,
    };
  }
}

class CaptureTaskResponse {
  CaptureTaskResponse({
    required this.taskId,
    required this.contextEdgeIds,
    required this.dependencyEdgeIds,
  });

  final String taskId;
  final List<String> contextEdgeIds;
  final List<String> dependencyEdgeIds;

  factory CaptureTaskResponse.fromJson(Map<String, dynamic> json) {
    return CaptureTaskResponse(
      taskId: json['task_id'] as String,
      contextEdgeIds: (json['context_edge_ids'] as List<dynamic>)
          .map((e) => e as String)
          .toList(),
      dependencyEdgeIds: (json['dependency_edge_ids'] as List<dynamic>)
          .map((e) => e as String)
          .toList(),
    );
  }
}

class CaptureNoteRequest {
  CaptureNoteRequest({
    required this.text,
    this.title,
  });

  final String text;
  final String? title;

  Map<String, dynamic> toJson() {
    return {
      'text': text,
      if (title != null) 'title': title,
    };
  }
}

class CaptureNoteResponse {
  CaptureNoteResponse({required this.noteId});

  final String noteId;

  factory CaptureNoteResponse.fromJson(Map<String, dynamic> json) {
    return CaptureNoteResponse(noteId: json['note_id'] as String);
  }
}

class HealthStatus {
  HealthStatus({required this.status});
  final String status;

  factory HealthStatus.fromJson(Map<String, dynamic> json) {
    return HealthStatus(status: json['status'] as String);
  }
}

class SecretaryObject {
  SecretaryObject({
    required this.id,
    required this.kind,
    required this.title,
    this.body,
    this.provider,
    this.externalId,
    this.canonicalUri,
    this.status,
    this.startAt,
    this.dueAt,
    this.occurredAt,
    this.deletedAt,
    required this.metadata,
    required this.origin,
    required this.state,
    this.confidence,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String kind;
  final String title;
  final String? body;
  final String? provider;
  final String? externalId;
  final String? canonicalUri;
  final String? status;
  final String? startAt;
  final String? dueAt;
  final String? occurredAt;
  final String? deletedAt;
  final Map<String, dynamic> metadata;
  final String origin;
  final String state;
  final double? confidence;
  final String createdAt;
  final String updatedAt;

  factory SecretaryObject.fromJson(Map<String, dynamic> json) {
    return SecretaryObject(
      id: json['id'] as String,
      kind: json['kind'] as String,
      title: json['title'] as String,
      body: json['body'] as String?,
      provider: json['provider'] as String?,
      externalId: json['external_id'] as String?,
      canonicalUri: json['canonical_uri'] as String?,
      status: json['status'] as String?,
      startAt: json['start_at'] as String?,
      dueAt: json['due_at'] as String?,
      occurredAt: json['occurred_at'] as String?,
      deletedAt: json['deleted_at'] as String?,
      metadata: Map<String, dynamic>.from(
        (json['metadata'] as Map?) ?? const <String, dynamic>{},
      ),
      origin: json['origin'] as String,
      state: json['state'] as String,
      confidence: (json['confidence'] as num?)?.toDouble(),
      createdAt: json['created_at'] as String,
      updatedAt: json['updated_at'] as String,
    );
  }
}

class SecretaryEdge {
  SecretaryEdge({
    required this.id,
    required this.sourceId,
    required this.targetId,
    required this.type,
    required this.origin,
    this.confidence,
    required this.state,
    required this.metadata,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String sourceId;
  final String targetId;
  final String type;
  final String origin;
  final double? confidence;
  final String state;
  final Map<String, dynamic> metadata;
  final String createdAt;
  final String updatedAt;

  factory SecretaryEdge.fromJson(Map<String, dynamic> json) {
    return SecretaryEdge(
      id: json['id'] as String,
      sourceId: json['source_id'] as String,
      targetId: json['target_id'] as String,
      type: json['type'] as String,
      origin: json['origin'] as String,
      confidence: (json['confidence'] as num?)?.toDouble(),
      state: json['state'] as String,
      metadata: Map<String, dynamic>.from(
        (json['metadata'] as Map?) ?? const <String, dynamic>{},
      ),
      createdAt: json['created_at'] as String,
      updatedAt: json['updated_at'] as String,
    );
  }
}

class NeighborOut {
  NeighborOut({
    required this.object,
    required this.edge,
    required this.direction,
  });

  final SecretaryObject object;
  final SecretaryEdge edge;
  final String direction;

  factory NeighborOut.fromJson(Map<String, dynamic> json) {
    return NeighborOut(
      object: SecretaryObject.fromJson(json['object'] as Map<String, dynamic>),
      edge: SecretaryEdge.fromJson(json['edge'] as Map<String, dynamic>),
      direction: json['direction'] as String,
    );
  }
}

class NeighborsResponse {
  NeighborsResponse({required this.objectId, required this.neighbors});

  final String objectId;
  final List<NeighborOut> neighbors;

  factory NeighborsResponse.fromJson(Map<String, dynamic> json) {
    return NeighborsResponse(
      objectId: json['object_id'] as String,
      neighbors: (json['neighbors'] as List<dynamic>)
          .map((e) => NeighborOut.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

class ContextResponse {
  ContextResponse({
    required this.object,
    required this.edges,
    required this.neighbors,
  });

  final SecretaryObject object;
  final List<SecretaryEdge> edges;
  final List<SecretaryObject> neighbors;

  factory ContextResponse.fromJson(Map<String, dynamic> json) {
    return ContextResponse(
      object: SecretaryObject.fromJson(json['object'] as Map<String, dynamic>),
      edges: (json['edges'] as List<dynamic>)
          .map((e) => SecretaryEdge.fromJson(e as Map<String, dynamic>))
          .toList(),
      neighbors: (json['neighbors'] as List<dynamic>)
          .map((e) => SecretaryObject.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

class NotificationOut {
  NotificationOut({
    required this.id,
    required this.title,
    this.body,
    required this.priority,
    required this.status,
    this.sourceObjectId,
    this.relatedObjectId,
    this.resultObjectId,
    required this.proposal,
    this.readAt,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String title;
  final String? body;
  final String priority;
  final String status;
  final String? sourceObjectId;
  final String? relatedObjectId;
  final String? resultObjectId;
  final Map<String, dynamic> proposal;
  final String? readAt;
  final String createdAt;
  final String updatedAt;

  String? get proposalType => proposal['type'] as String?;

  String? get proposedAction => proposal['action'] as String?;

  String? get proposalDescription => proposal['description'] as String? ?? body;

  factory NotificationOut.fromJson(Map<String, dynamic> json) {
    return NotificationOut(
      id: json['id'] as String,
      title: json['title'] as String,
      body: json['body'] as String?,
      priority: json['priority'] as String,
      status: json['status'] as String,
      sourceObjectId: json['source_object_id'] as String?,
      relatedObjectId: json['related_object_id'] as String?,
      resultObjectId: json['result_object_id'] as String?,
      proposal: Map<String, dynamic>.from(
        (json['proposal'] as Map?) ?? const <String, dynamic>{},
      ),
      readAt: json['read_at'] as String?,
      createdAt: json['created_at'] as String,
      updatedAt: json['updated_at'] as String,
    );
  }
}

class InboxSourceObjectOut {
  InboxSourceObjectOut({
    required this.id,
    required this.title,
    required this.kind,
    required this.provider,
    required this.origin,
    required this.state,
    required this.status,
    required this.primaryAt,
    required this.excerpt,
  });

  final String id;
  final String title;
  final String kind;
  final String? provider;
  final String origin;
  final String state;
  final String? status;
  final String? primaryAt;
  final String? excerpt;

  factory InboxSourceObjectOut.fromJson(Map<String, dynamic> json) {
    return InboxSourceObjectOut(
      id: json['id'] as String,
      title: json['title'] as String,
      kind: json['kind'] as String,
      provider: json['provider'] as String?,
      origin: json['origin'] as String? ?? 'source',
      state: json['state'] as String,
      status: json['status'] as String?,
      primaryAt: json['primary_at'] as String?,
      excerpt: json['excerpt'] as String?,
    );
  }
}

class SourceSyncStatusOut {
  SourceSyncStatusOut({
    required this.source,
    required this.provider,
    required this.accountId,
    required this.accountLabel,
    required this.status,
    this.enabled,
    required this.lastSuccessAt,
    required this.lastAttemptAt,
    required this.nextSyncAt,
    required this.lastError,
  });

  final String source;
  final String provider;
  final String accountId;
  final String accountLabel;
  final String status;
  final bool? enabled;
  final String? lastSuccessAt;
  final String? lastAttemptAt;
  final String? nextSyncAt;
  final String? lastError;

  factory SourceSyncStatusOut.fromJson(Map<String, dynamic> json) {
    return SourceSyncStatusOut(
      source: json['source'] as String,
      provider: json['provider'] as String,
      accountId: json['account_id'] as String,
      accountLabel: json['account_label'] as String,
      status: json['status'] as String,
      enabled: json['enabled'] as bool?,
      lastSuccessAt: json['last_success_at'] as String?,
      lastAttemptAt: json['last_attempt_at'] as String?,
      nextSyncAt: json['next_sync_at'] as String?,
      lastError: json['last_error'] as String?,
    );
  }
}

class InboxOut {
  InboxOut({
    required this.unresolvedNotifications,
    required this.recentSourceObjects,
    required this.sourceSyncStatus,
  });

  final List<NotificationOut> unresolvedNotifications;
  final List<InboxSourceObjectOut> recentSourceObjects;
  final List<SourceSyncStatusOut> sourceSyncStatus;

  factory InboxOut.fromJson(Map<String, dynamic> json) {
    return InboxOut(
      unresolvedNotifications:
          (json['unresolved_notifications'] as List<dynamic>)
              .map((e) => NotificationOut.fromJson(e as Map<String, dynamic>))
              .toList(),
      recentSourceObjects: (json['recent_source_objects'] as List<dynamic>)
          .map((e) => InboxSourceObjectOut.fromJson(e as Map<String, dynamic>))
          .toList(),
      sourceSyncStatus: (json['source_sync_status'] as List<dynamic>)
          .map((e) => SourceSyncStatusOut.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

class TodayOut {
  TodayOut({
    required this.date,
    required this.timezone,
    required this.dayStart,
    required this.tasks,
    required this.calendarEvents,
    required this.notifications,
  });

  final String date;
  final String timezone;
  final String dayStart;
  final List<SecretaryObject> tasks;
  final List<SecretaryObject> calendarEvents;
  final List<NotificationOut> notifications;

  factory TodayOut.fromJson(Map<String, dynamic> json) {
    return TodayOut(
      date: json['date'] as String,
      timezone: json['timezone'] as String,
      dayStart: json['day_start'] as String,
      tasks: (json['tasks'] as List<dynamic>)
          .map((e) => SecretaryObject.fromJson(e as Map<String, dynamic>))
          .toList(),
      calendarEvents: (json['calendar_events'] as List<dynamic>)
          .map((e) => SecretaryObject.fromJson(e as Map<String, dynamic>))
          .toList(),
      notifications: (json['notifications'] as List<dynamic>)
          .map((e) => NotificationOut.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  /// Task is overdue when its due instant is before the Secretary local day start.
  bool isTaskOverdue(SecretaryObject task) {
    final dueAt = task.dueAt;
    if (dueAt == null) {
      return false;
    }
    final due = DateTime.tryParse(dueAt);
    final start = DateTime.tryParse(dayStart);
    if (due == null || start == null) {
      return false;
    }
    return due.isBefore(start);
  }
}

class CaptureContextRef {
  const CaptureContextRef({
    required this.id,
    required this.title,
    required this.kind,
  });

  final String id;
  final String title;
  final String kind;

  String get displayLabel {
    final normalizedKind = kind.trim();
    if (normalizedKind.isEmpty) {
      return title;
    }
    return '$normalizedKind: $title';
  }
}

class AssistantHistoryMessage {
  AssistantHistoryMessage({required this.role, required this.content});

  final String role;
  final String content;

  Map<String, dynamic> toJson() => {'role': role, 'content': content};
}

class AssistantMessageRequest {
  AssistantMessageRequest({
    required this.message,
    this.history = const [],
    this.contextObjectId,
    this.contextNotificationId,
    this.clientTimezoneId,
    this.clientUtcOffsetMinutes,
  });

  final String message;
  final List<AssistantHistoryMessage> history;
  final String? contextObjectId;
  final String? contextNotificationId;
  final String? clientTimezoneId;
  final int? clientUtcOffsetMinutes;

  Map<String, dynamic> toJson() {
    return {
      'message': message,
      'history': history.map((e) => e.toJson()).toList(),
      if (contextObjectId != null) 'context_object_id': contextObjectId,
      if (contextNotificationId != null)
        'context_notification_id': contextNotificationId,
      if (clientTimezoneId != null) 'client_timezone_id': clientTimezoneId,
      if (clientUtcOffsetMinutes != null)
        'client_utc_offset_minutes': clientUtcOffsetMinutes,
    };
  }
}

class AssistantReference {
  AssistantReference({
    required this.objectId,
    required this.title,
    required this.kind,
    this.canonicalUri,
  });

  final String objectId;
  final String title;
  final String kind;
  final String? canonicalUri;

  factory AssistantReference.fromJson(Map<String, dynamic> json) {
    return AssistantReference(
      objectId: json['object_id'] as String,
      title: json['title'] as String,
      kind: json['kind'] as String,
      canonicalUri: json['canonical_uri'] as String?,
    );
  }

  String get displayLabel => '$kind: $title';
}

class AssistantMessageResponse {
  AssistantMessageResponse({
    required this.answer,
    required this.references,
    required this.affectedObjects,
    this.pendingActionPlan,
  });

  final String answer;
  final List<AssistantReference> references;
  final List<AssistantAffectedObject> affectedObjects;
  final PendingActionPlan? pendingActionPlan;

  factory AssistantMessageResponse.fromJson(Map<String, dynamic> json) {
    final pendingRaw = json['pending_action_plan'];
    return AssistantMessageResponse(
      answer: json['answer'] as String,
      references: (json['references'] as List<dynamic>)
          .map((e) => AssistantReference.fromJson(e as Map<String, dynamic>))
          .toList(),
      affectedObjects: (json['affected_objects'] as List<dynamic>)
          .map((e) =>
              AssistantAffectedObject.fromJson(e as Map<String, dynamic>))
          .toList(),
      pendingActionPlan: pendingRaw == null
          ? null
          : PendingActionPlan.fromJson(pendingRaw as Map<String, dynamic>),
    );
  }
}

class PendingAction {
  PendingAction({required this.toolName, required this.arguments});

  final String toolName;
  final Map<String, dynamic> arguments;

  factory PendingAction.fromJson(Map<String, dynamic> json) {
    return PendingAction(
      toolName: json['tool_name'] as String,
      arguments: Map<String, dynamic>.from(json['arguments'] as Map),
    );
  }

  String get displayLabel {
    final objectId = _frozenObjectId(arguments);
    switch (toolName) {
      case 'create_task':
        final title = arguments['title'];
        if (title is String && title.trim().isNotEmpty) {
          return 'Create task: $title';
        }
        return 'Create task';
      case 'update_task':
        if (objectId != null) {
          return 'Update task: $objectId';
        }
        return 'Update task';
      case 'set_task_status':
        final status = arguments['status'];
        final statusText =
            status is String && status.trim().isNotEmpty ? status : 'status';
        if (objectId != null) {
          return 'Set task status: $objectId -> $statusText';
        }
        return 'Set task status: $statusText';
      case 'delete_task':
        if (objectId != null) {
          return 'Delete task: $objectId';
        }
        return 'Delete task';
      case 'link_objects':
        return 'Link objects';
      default:
        return toolName.replaceAll('_', ' ');
    }
  }

  static String? _frozenObjectId(Map<String, dynamic> arguments) {
    final raw = arguments['object_id'];
    if (raw is String && raw.trim().isNotEmpty) {
      return raw.trim();
    }
    return null;
  }
}

class PendingActionPlan {
  PendingActionPlan({
    required this.id,
    required this.status,
    required this.expiresAt,
    required this.actions,
  });

  final String id;
  final String status;
  final String expiresAt;
  final List<PendingAction> actions;

  factory PendingActionPlan.fromJson(Map<String, dynamic> json) {
    return PendingActionPlan(
      id: json['id'] as String,
      status: json['status'] as String,
      expiresAt: json['expires_at'] as String,
      actions: (json['actions'] as List<dynamic>)
          .map((e) => PendingAction.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

class ActionPlanResponse {
  ActionPlanResponse({
    required this.id,
    required this.status,
    required this.expiresAt,
    required this.actions,
    this.result,
    this.failure,
  });

  final String id;
  final String status;
  final String expiresAt;
  final List<PendingAction> actions;
  final Map<String, dynamic>? result;
  final String? failure;

  factory ActionPlanResponse.fromJson(Map<String, dynamic> json) {
    final resultRaw = json['result'];
    return ActionPlanResponse(
      id: json['id'] as String,
      status: json['status'] as String,
      expiresAt: json['expires_at'] as String,
      actions: (json['actions'] as List<dynamic>)
          .map((e) => PendingAction.fromJson(e as Map<String, dynamic>))
          .toList(),
      result: resultRaw == null
          ? null
          : Map<String, dynamic>.from(resultRaw as Map),
      failure: json['failure'] as String?,
    );
  }

  /// Parses structured action-plan terminal responses; returns null for generic conflicts.
  static ActionPlanResponse? tryParse(Map<String, dynamic> json) {
    if (json.containsKey('detail') && !json.containsKey('actions')) {
      return null;
    }
    final id = json['id'];
    final status = json['status'];
    final expiresAt = json['expires_at'];
    final actions = json['actions'];
    if (id is! String ||
        status is! String ||
        expiresAt is! String ||
        actions is! List) {
      return null;
    }
    try {
      return ActionPlanResponse.fromJson(json);
    } catch (_) {
      return null;
    }
  }
}

class ActionPlanResumeResponse {
  ActionPlanResumeResponse({
    required this.answer,
    required this.affectedObjects,
  });

  final String answer;
  final List<AssistantAffectedObject> affectedObjects;

  factory ActionPlanResumeResponse.fromJson(Map<String, dynamic> json) {
    return ActionPlanResumeResponse(
      answer: json['answer'] as String,
      affectedObjects: (json['affected_objects'] as List<dynamic>)
          .map((e) =>
              AssistantAffectedObject.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

class AssistantAffectedObject {
  AssistantAffectedObject({
    required this.objectId,
    required this.title,
    required this.kind,
    required this.state,
    this.status,
  });

  final String objectId;
  final String title;
  final String kind;
  final String state;
  final String? status;

  factory AssistantAffectedObject.fromJson(Map<String, dynamic> json) {
    return AssistantAffectedObject(
      objectId: json['object_id'] as String,
      title: json['title'] as String,
      kind: json['kind'] as String,
      state: json['state'] as String,
      status: json['status'] as String?,
    );
  }

  String get lifecycleLabel {
    if (status != null && status!.trim().isNotEmpty) {
      return status!;
    }
    return state;
  }

  String get displayLabel => '$kind: $title — $lifecycleLabel';
}

class AssistantContextRef {
  const AssistantContextRef({
    required this.id,
    required this.title,
    required this.kind,
  });

  final String id;
  final String title;
  final String kind;

  String get displayLabel => '$kind — $title';
}

class SearchResultSnippet {
  static String fromBody(String? body, {int maxChars = 200}) {
    if (body == null || body.trim().isEmpty) {
      return '';
    }
    final normalized = body.replaceAll(RegExp(r'\s+'), ' ').trim();
    if (normalized.length <= maxChars) {
      return normalized;
    }
    return '${normalized.substring(0, maxChars)}…';
  }
}

extension SecretaryObjectLifecycle on SecretaryObject {
  String get lifecycleLabel {
    if (status != null && status!.trim().isNotEmpty) {
      if (status == 'completed') {
        return 'completed';
      }
      return status!;
    }
    return state;
  }

  bool get isDeletedTask => kind == 'task' && status == 'deleted';

  bool get isTombstoned => deletedAt != null;
}

class GraphWorkspaceOut {
  GraphWorkspaceOut({
    this.rootId,
    required this.seedIds,
    required this.nodes,
    required this.edges,
    required this.truncated,
  });

  final String? rootId;
  final List<String> seedIds;
  final List<SecretaryObject> nodes;
  final List<SecretaryEdge> edges;
  final bool truncated;

  factory GraphWorkspaceOut.fromJson(Map<String, dynamic> json) {
    return GraphWorkspaceOut(
      rootId: json['root_id'] as String?,
      seedIds:
          (json['seed_ids'] as List<dynamic>).map((e) => e as String).toList(),
      nodes: (json['nodes'] as List<dynamic>)
          .map((e) => SecretaryObject.fromJson(e as Map<String, dynamic>))
          .toList(),
      edges: (json['edges'] as List<dynamic>)
          .map((e) => SecretaryEdge.fromJson(e as Map<String, dynamic>))
          .toList(),
      truncated: json['truncated'] as bool? ?? false,
    );
  }
}

class OpenTarget {
  OpenTarget({
    required this.available,
    required this.action,
    required this.label,
    this.url,
    this.deviceKey,
    this.localPath,
    this.reason,
  });

  final bool available;
  final String action;
  final String label;
  final String? url;
  final String? deviceKey;
  final String? localPath;
  final String? reason;

  factory OpenTarget.fromJson(Map<String, dynamic> json) {
    return OpenTarget(
      available: json['available'] as bool? ?? false,
      action: json['action'] as String? ?? 'unavailable',
      label: json['label'] as String? ?? 'Открыть в источнике',
      url: json['url'] as String?,
      deviceKey: json['device_key'] as String?,
      localPath: json['local_path'] as String?,
      reason: json['reason'] as String?,
    );
  }
}

class ClientFileIntakeResult {
  ClientFileIntakeResult({
    required this.objectId,
    required this.status,
    required this.jobsEnqueued,
    required this.representationsCreated,
    required this.metadataOnly,
  });

  final String objectId;
  final String status;
  final int jobsEnqueued;
  final int representationsCreated;
  final bool metadataOnly;

  factory ClientFileIntakeResult.fromJson(Map<String, dynamic> json) {
    return ClientFileIntakeResult(
      objectId: json['object_id'] as String,
      status: json['status'] as String,
      jobsEnqueued: json['jobs_enqueued'] as int? ?? 0,
      representationsCreated: json['representations_created'] as int? ?? 0,
      metadataOnly: json['metadata_only'] as bool? ?? false,
    );
  }
}

class ClientFolderIntakeResult {
  ClientFolderIntakeResult({
    required this.objectId,
    required this.status,
  });

  final String objectId;
  final String status;

  factory ClientFolderIntakeResult.fromJson(Map<String, dynamic> json) {
    return ClientFolderIntakeResult(
      objectId: json['object_id'] as String,
      status: json['status'] as String,
    );
  }
}

class IntakeLinkResult {
  IntakeLinkResult({
    required this.objectId,
    required this.provider,
    required this.kind,
    required this.status,
    required this.contentStatus,
    required this.contentJobsEnqueued,
  });

  final String objectId;
  final String provider;
  final String kind;
  final String status;
  final String contentStatus;
  final int contentJobsEnqueued;

  factory IntakeLinkResult.fromJson(Map<String, dynamic> json) {
    return IntakeLinkResult(
      objectId: json['object_id'] as String,
      provider: json['provider'] as String,
      kind: json['kind'] as String,
      status: json['status'] as String,
      contentStatus: json['content_status'] as String,
      contentJobsEnqueued: json['content_jobs_enqueued'] as int,
    );
  }
}

class LocalDeviceRegisterResult {
  LocalDeviceRegisterResult({
    required this.deviceId,
    required this.deviceKey,
    required this.displayName,
    required this.created,
  });

  final String deviceId;
  final String deviceKey;
  final String displayName;
  final bool created;

  factory LocalDeviceRegisterResult.fromJson(Map<String, dynamic> json) {
    return LocalDeviceRegisterResult(
      deviceId: json['device_id'] as String,
      deviceKey: json['device_key'] as String,
      displayName: json['display_name'] as String,
      created: json['created'] as bool? ?? false,
    );
  }
}

class TaskPatchRequest {
  String? title;
  bool titleSet = false;
  String? body;
  bool bodySet = false;
  String? dueAt;
  bool dueAtSet = false;

  bool get isEmpty => !titleSet && !bodySet && !dueAtSet;

  Map<String, dynamic> toJson() {
    final result = <String, dynamic>{};
    if (titleSet) {
      result['title'] = title;
    }
    if (bodySet) {
      result['body'] = body;
    }
    if (dueAtSet) {
      result['due_at'] = dueAt;
    }
    return result;
  }
}

class TaskMutationResponse {
  TaskMutationResponse({required this.object, required this.changed});

  final SecretaryObject object;
  final bool changed;

  factory TaskMutationResponse.fromJson(Map<String, dynamic> json) {
    return TaskMutationResponse(
      object: SecretaryObject.fromJson(json['object'] as Map<String, dynamic>),
      changed: json['changed'] as bool? ?? false,
    );
  }
}

class TaskStatusResponse {
  TaskStatusResponse({
    required this.object,
    required this.changed,
    this.previousStatus,
    required this.newStatus,
  });

  final SecretaryObject object;
  final bool changed;
  final String? previousStatus;
  final String newStatus;

  factory TaskStatusResponse.fromJson(Map<String, dynamic> json) {
    return TaskStatusResponse(
      object: SecretaryObject.fromJson(json['object'] as Map<String, dynamic>),
      changed: json['changed'] as bool? ?? false,
      previousStatus: json['previous_status'] as String?,
      newStatus: json['new_status'] as String,
    );
  }
}

class ObjectDeleteResponse {
  ObjectDeleteResponse({
    required this.objectId,
    required this.deletedAt,
    required this.alreadyDeleted,
  });

  final String objectId;
  final String deletedAt;
  final bool alreadyDeleted;

  factory ObjectDeleteResponse.fromJson(Map<String, dynamic> json) {
    return ObjectDeleteResponse(
      objectId: json['object_id'] as String,
      deletedAt: json['deleted_at'] as String,
      alreadyDeleted: json['already_deleted'] as bool? ?? false,
    );
  }
}

class RelationCreateResponse {
  RelationCreateResponse({required this.edge, required this.created});

  final SecretaryEdge edge;
  final bool created;

  factory RelationCreateResponse.fromJson(Map<String, dynamic> json) {
    return RelationCreateResponse(
      edge: SecretaryEdge.fromJson(json['edge'] as Map<String, dynamic>),
      created: json['created'] as bool? ?? false,
    );
  }
}

class RelationDecisionResponse {
  RelationDecisionResponse({required this.edge});

  final SecretaryEdge edge;

  factory RelationDecisionResponse.fromJson(Map<String, dynamic> json) {
    return RelationDecisionResponse(
      edge: SecretaryEdge.fromJson(json['edge'] as Map<String, dynamic>),
    );
  }
}

class SearchFacetValue {
  SearchFacetValue({required this.value, required this.count});

  final String value;
  final int count;

  factory SearchFacetValue.fromJson(Map<String, dynamic> json) {
    return SearchFacetValue(
      value: json['value'] as String,
      count: json['count'] as int,
    );
  }
}

class SearchFacetsOut {
  SearchFacetsOut({required this.kinds, required this.providers});

  final List<SearchFacetValue> kinds;
  final List<SearchFacetValue> providers;

  factory SearchFacetsOut.fromJson(Map<String, dynamic> json) {
    return SearchFacetsOut(
      kinds: (json['kinds'] as List<dynamic>)
          .map((row) => SearchFacetValue.fromJson(row as Map<String, dynamic>))
          .toList(),
      providers: (json['providers'] as List<dynamic>)
          .map((row) => SearchFacetValue.fromJson(row as Map<String, dynamic>))
          .toList(),
    );
  }
}

/// Recurring account sources with per-user sync preferences (PHASE 28C-A).
const List<String> supportedSourcePreferenceKeys = [
  'gmail',
  'google_calendar',
  'yandex_mail',
  'yandex_calendar',
  'mattermost',
];

class SourcePreference {
  SourcePreference({
    required this.source,
    required this.enabled,
    required this.syncIntervalSeconds,
    required this.defaultSyncIntervalSeconds,
    required this.minSyncIntervalSeconds,
    required this.maxSyncIntervalSeconds,
    required this.historyDays,
    required this.defaultHistoryDays,
    required this.minHistoryDays,
    required this.maxHistoryDays,
  });

  final String source;
  final bool enabled;
  final int syncIntervalSeconds;
  final int defaultSyncIntervalSeconds;
  final int minSyncIntervalSeconds;
  final int maxSyncIntervalSeconds;
  final int historyDays;
  final int defaultHistoryDays;
  final int minHistoryDays;
  final int maxHistoryDays;

  factory SourcePreference.fromJson(Map<String, dynamic> json) {
    return SourcePreference(
      source: json['source'] as String,
      enabled: json['enabled'] as bool,
      syncIntervalSeconds: json['sync_interval_seconds'] as int,
      defaultSyncIntervalSeconds: json['default_sync_interval_seconds'] as int,
      minSyncIntervalSeconds: json['min_sync_interval_seconds'] as int,
      maxSyncIntervalSeconds: json['max_sync_interval_seconds'] as int,
      historyDays: json['history_days'] as int,
      defaultHistoryDays: json['default_history_days'] as int,
      minHistoryDays: json['min_history_days'] as int,
      maxHistoryDays: json['max_history_days'] as int,
    );
  }
}

class SourcePreferenceList {
  SourcePreferenceList({required this.preferences});

  final List<SourcePreference> preferences;

  factory SourcePreferenceList.fromJson(Map<String, dynamic> json) {
    return SourcePreferenceList(
      preferences: (json['preferences'] as List<dynamic>)
          .map((e) => SourcePreference.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
