package com.example.personal_secretary.assistant

import android.app.Activity
import android.app.KeyguardManager
import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.provider.Settings
import android.service.voice.VoiceInteractionService
import com.example.personal_secretary.hardware.HardwareVoiceLog
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

class SystemAssistantPlugin(
    private val activity: Activity,
    messenger: BinaryMessenger,
) : MethodChannel.MethodCallHandler {
    private val channel = MethodChannel(messenger, SystemAssistantConstants.CHANNEL)

    init {
        channel.setMethodCallHandler(this)
        HardwareVoiceLog.line("SystemAssistantPlugin attached")
    }

    fun dispose() {
        channel.setMethodCallHandler(null)
    }

    fun emitAssistInvoke() {
        HardwareVoiceLog.line("onAssistInvoke")
        channel.invokeMethod("onAssistInvoke", null)
    }

    fun emitKeyguard(locked: Boolean) {
        channel.invokeMethod("onKeyguard", locked)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "getStatus" -> result.success(statusMap())
            "requestAssistantRole" -> {
                requestRole()
                result.success(null)
            }
            "dismiss" -> {
                if (activity is VoiceSessionActivity) {
                    activity.finish()
                }
                result.success(null)
            }
            else -> result.notImplemented()
        }
    }

    private fun requestRole() {
        val context = activity
        if (Build.VERSION.SDK_INT >= 29) {
            val roles = context.getSystemService(RoleManager::class.java)
            if (roles != null && roles.isRoleAvailable(RoleManager.ROLE_ASSISTANT)) {
                context.startActivity(roles.createRequestRoleIntent(RoleManager.ROLE_ASSISTANT))
                return
            }
        }
        val voiceInput = Intent(Settings.ACTION_VOICE_INPUT_SETTINGS)
        if (voiceInput.resolveActivity(context.packageManager) != null) {
            context.startActivity(voiceInput)
            return
        }
        context.startActivity(Intent(Settings.ACTION_SETTINGS))
    }

    private fun statusMap(): Map<String, Any?> {
        val keyguard = activity.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
        var isDefault = false
        var roleAvailable = false
        if (Build.VERSION.SDK_INT >= 29) {
            val roles = activity.getSystemService(RoleManager::class.java)
            roleAvailable = roles?.isRoleAvailable(RoleManager.ROLE_ASSISTANT) == true
            isDefault = roles?.isRoleHeld(RoleManager.ROLE_ASSISTANT) == true
        }
        if (!isDefault) {
            isDefault = VoiceInteractionService.isActiveService(
                activity,
                android.content.ComponentName(
                    activity,
                    SecretaryVoiceInteractionService::class.java,
                ),
            )
        }
        return mapOf(
            "ok" to true,
            "available" to true,
            "protocol" to SystemAssistantConstants.PROTOCOL,
            "isDefaultAssistant" to isDefault,
            "roleManagerAvailable" to roleAvailable,
            "keyguardLocked" to keyguard.isKeyguardLocked,
        )
    }
}

fun Intent.hasVoiceTriggerExtra(): Boolean {
    return getBooleanExtra(SystemAssistantConstants.EXTRA_VOICE_TRIGGER, false)
}

fun consumeVoiceTrigger(intent: Intent?): Boolean {
    if (intent == null || !intent.hasVoiceTriggerExtra()) {
        return false
    }
    intent.removeExtra(SystemAssistantConstants.EXTRA_VOICE_TRIGGER)
    return true
}

fun applyLockScreenFlags(activity: Activity) {
    if (Build.VERSION.SDK_INT >= 27) {
        activity.setShowWhenLocked(true)
        activity.setTurnScreenOn(true)
    } else {
        @Suppress("DEPRECATION")
        activity.window.addFlags(
            android.view.WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                android.view.WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON,
        )
    }
}

fun launchUnlockedVoice(context: Context) {
    val intent = Intent().setClassName(
        context,
        "com.example.personal_secretary.MainActivity",
    ).apply {
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
        putExtra(SystemAssistantConstants.EXTRA_VOICE_TRIGGER, true)
    }
    context.startActivity(intent)
}

fun launchLockedVoice(context: Context) {
    val intent = Intent(context, VoiceSessionActivity::class.java).apply {
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
    }
    context.startActivity(intent)
}
