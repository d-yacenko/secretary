class UserMe {
  UserMe({required this.id, required this.displayName, required this.createdAt});

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

class GoogleConnection {
  GoogleConnection({
    required this.connected,
    this.email,
    required this.gmailAvailable,
    required this.calendarAvailable,
  });

  final bool connected;
  final String? email;
  final bool gmailAvailable;
  final bool calendarAvailable;

  factory GoogleConnection.fromJson(Map<String, dynamic> json) {
    return GoogleConnection(
      connected: json['connected'] as bool,
      email: json['email'] as String?,
      gmailAvailable: json['gmail_available'] as bool? ?? false,
      calendarAvailable: json['calendar_available'] as bool? ?? false,
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

class Connections {
  Connections({
    required this.google,
    required this.yandexMail,
    required this.yandexCalendar,
  });

  final GoogleConnection google;
  final YandexMailConnection yandexMail;
  final YandexCalendarConnection yandexCalendar;

  factory Connections.fromJson(Map<String, dynamic> json) {
    return Connections(
      google: GoogleConnection.fromJson(json['google'] as Map<String, dynamic>),
      yandexMail:
          YandexMailConnection.fromJson(json['yandex_mail'] as Map<String, dynamic>),
      yandexCalendar: YandexCalendarConnection.fromJson(
        json['yandex_calendar'] as Map<String, dynamic>,
      ),
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

  String? get proposalDescription =>
      proposal['description'] as String? ?? body;

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
  });

  final String message;
  final List<AssistantHistoryMessage> history;
  final String? contextObjectId;
  final String? contextNotificationId;

  Map<String, dynamic> toJson() {
    return {
      'message': message,
      'history': history.map((e) => e.toJson()).toList(),
      if (contextObjectId != null) 'context_object_id': contextObjectId,
      if (contextNotificationId != null)
        'context_notification_id': contextNotificationId,
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
  });

  final String answer;
  final List<AssistantReference> references;
  final List<AssistantAffectedObject> affectedObjects;

  factory AssistantMessageResponse.fromJson(Map<String, dynamic> json) {
    return AssistantMessageResponse(
      answer: json['answer'] as String,
      references: (json['references'] as List<dynamic>)
          .map((e) => AssistantReference.fromJson(e as Map<String, dynamic>))
          .toList(),
      affectedObjects: (json['affected_objects'] as List<dynamic>)
          .map((e) => AssistantAffectedObject.fromJson(e as Map<String, dynamic>))
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
  });

  final String objectId;
  final String title;
  final String kind;
  final String state;

  factory AssistantAffectedObject.fromJson(Map<String, dynamic> json) {
    return AssistantAffectedObject(
      objectId: json['object_id'] as String,
      title: json['title'] as String,
      kind: json['kind'] as String,
      state: json['state'] as String,
    );
  }
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
