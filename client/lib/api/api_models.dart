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
