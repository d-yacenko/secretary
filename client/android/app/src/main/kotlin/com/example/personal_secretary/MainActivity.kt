package com.example.personal_secretary

import android.view.KeyEvent
import com.example.personal_secretary.hardware.HardwareVoiceLog
import com.example.personal_secretary.hardware.HardwareVoicePlugin
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine

class MainActivity : FlutterActivity() {
    private var hardwareVoice: HardwareVoicePlugin? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        hardwareVoice = HardwareVoicePlugin(this, flutterEngine.dartExecutor.binaryMessenger)
        HardwareVoiceLog.line("MainActivity plugin attached")
    }

    override fun cleanUpFlutterEngine(flutterEngine: FlutterEngine) {
        HardwareVoiceLog.line("MainActivity plugin cleanup")
        hardwareVoice?.dispose()
        hardwareVoice = null
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
}
