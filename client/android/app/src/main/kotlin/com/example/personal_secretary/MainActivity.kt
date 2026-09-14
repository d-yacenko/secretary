package com.example.personal_secretary

import android.content.Intent
import android.os.Bundle
import android.view.KeyEvent
import com.example.personal_secretary.assistant.SystemAssistantPlugin
import com.example.personal_secretary.assistant.consumeVoiceTrigger
import com.example.personal_secretary.hardware.HardwareVoiceLog
import com.example.personal_secretary.hardware.HardwareVoicePlugin
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine

class MainActivity : FlutterActivity() {
    private var hardwareVoice: HardwareVoicePlugin? = null
    private var systemAssistant: SystemAssistantPlugin? = null
    private var pendingAssist = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (consumeVoiceTrigger(intent)) {
            pendingAssist = true
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (consumeVoiceTrigger(intent)) {
            pendingAssist = true
            deliverPendingAssist()
        }
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        hardwareVoice = HardwareVoicePlugin(this, flutterEngine.dartExecutor.binaryMessenger)
        systemAssistant = SystemAssistantPlugin(this, flutterEngine.dartExecutor.binaryMessenger)
        HardwareVoiceLog.line("MainActivity plugin attached")
    }

    override fun onResume() {
        super.onResume()
        deliverPendingAssist()
    }

    override fun cleanUpFlutterEngine(flutterEngine: FlutterEngine) {
        HardwareVoiceLog.line("MainActivity plugin cleanup")
        hardwareVoice?.dispose()
        hardwareVoice = null
        systemAssistant?.dispose()
        systemAssistant = null
        super.cleanUpFlutterEngine(flutterEngine)
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        val plugin = hardwareVoice
        if (plugin == null) {
            HardwareVoiceLog.line(
                "dispatchKeyEvent plugin=null action=${event.action} keyCode=${event.keyCode}",
            )
            return super.dispatchKeyEvent(event)
        }
        if (plugin.handleKeyEvent(event)) {
            return true
        }
        return super.dispatchKeyEvent(event)
    }

    override fun onPause() {
        hardwareVoice?.onHostPause()
        super.onPause()
    }

    private fun deliverPendingAssist() {
        if (!pendingAssist) {
            return
        }
        val plugin = systemAssistant ?: return
        pendingAssist = false
        plugin.emitAssistInvoke()
    }
}
