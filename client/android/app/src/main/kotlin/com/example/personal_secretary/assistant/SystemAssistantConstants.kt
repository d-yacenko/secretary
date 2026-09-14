package com.example.personal_secretary.assistant

object SystemAssistantConstants {
    const val CHANNEL = "secretary/system_assistant"
    const val PROTOCOL = "secretary.system_assistant.v1"
    const val EXTRA_VOICE_TRIGGER = "secretary.voice_trigger"
    const val ROUTE_VOICE_SESSION = "/voice_session"
    const val REQUEST_ASSISTANT_ROLE = 7101
    const val LOCKED_LAUNCH_DEBOUNCE_MS = 800L

    const val LOCKED_LAUNCH_FLAGS =
        android.content.Intent.FLAG_ACTIVITY_NEW_TASK or
            android.content.Intent.FLAG_ACTIVITY_SINGLE_TOP or
            android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP
}
