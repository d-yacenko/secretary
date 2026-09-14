package com.example.personal_secretary

import android.view.KeyEvent
import com.example.personal_secretary.hardware.HardwareVoicePlugin
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine

class MainActivity : FlutterActivity() {
    private var hardwareVoice: HardwareVoicePlugin? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        hardwareVoice = HardwareVoicePlugin(this, flutterEngine.dartExecutor.binaryMessenger)
    }

    override fun cleanUpFlutterEngine(flutterEngine: FlutterEngine) {
        hardwareVoice?.dispose()
        hardwareVoice = null
        super.cleanUpFlutterEngine(flutterEngine)
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        val plugin = hardwareVoice
        if (plugin != null && plugin.handleKeyEvent(event)) {
            return true
        }
        return super.dispatchKeyEvent(event)
    }

    override fun onPause() {
        hardwareVoice?.onHostPause()
        super.onPause()
    }
}
