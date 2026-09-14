package com.example.personal_secretary.hardware

import android.content.Context
import android.media.AudioManager
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

class HardwareVoicePlugin(
    private val context: Context,
    messenger: BinaryMessenger,
    private val channel: MethodChannel = MethodChannel(
        messenger,
        HardwareVoiceConstants.CHANNEL,
    ),
) : MethodChannel.MethodCallHandler, HardwareVoiceCallbacks, HardwareVoiceScheduler {
    private val handler = Handler(Looper.getMainLooper())
    private val posted = mutableMapOf<String, Runnable>()
    private val engine = HardwareVoiceEngine(this, this)

    init {
        channel.setMethodCallHandler(this)
    }

    fun dispose() {
        channel.setMethodCallHandler(null)
        posted.values.forEach { handler.removeCallbacks(it) }
        posted.clear()
    }

    fun onHostPause() {
        engine.onHostPause()
    }

    fun handleKeyEvent(event: KeyEvent): Boolean {
        val name = try {
            KeyEvent.keyCodeToString(event.keyCode)
        } catch (_: Throwable) {
            null
        }
        val stroke = HardwareKeyStroke(
            keyCode = event.keyCode,
            scanCode = event.scanCode,
            repeatCount = event.repeatCount,
            isDown = event.action == KeyEvent.ACTION_DOWN,
            eventTimeMs = event.eventTime,
            androidKeyName = name,
        )
        return engine.onKey(stroke)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "configure" -> {
                val enabled = call.argument<Boolean>("enabled") ?: false
                val keyCode = call.argument<Int>("keyCode") ?: 0
                val scanCode = call.argument<Int>("scanCode") ?: 0
                val gestureRaw = call.argument<String>("gesture") ?: "single"
                val gesture =
                    if (gestureRaw == "double") {
                        HardwareVoiceGesture.DOUBLE
                    } else {
                        HardwareVoiceGesture.SINGLE
                    }
                val binding = HardwareVoiceNativeBinding(
                    enabled = enabled,
                    keyCode = if (keyCode == HardwareVoiceConstants.KEYCODE_VOLUME_UP) {
                        HardwareVoiceConstants.KEYCODE_VOLUME_UP
                    } else {
                        keyCode
                    },
                    scanCode = if (keyCode == HardwareVoiceConstants.KEYCODE_VOLUME_UP) 0 else scanCode,
                    gesture = if (keyCode == HardwareVoiceConstants.KEYCODE_VOLUME_UP) {
                        HardwareVoiceGesture.DOUBLE
                    } else {
                        gesture
                    },
                )
                engine.configure(binding)
                result.success(null)
            }
            "startLearn" -> {
                val timeout = (call.argument<Int>("timeoutMs") ?: HardwareVoiceConstants.LEARN_TIMEOUT_MS.toInt()).toLong()
                engine.startLearn(timeout)
                result.success(null)
            }
            "cancelLearn" -> {
                engine.cancelLearn()
                result.success(null)
            }
            "startTest" -> {
                val timeout = (call.argument<Int>("timeoutMs") ?: HardwareVoiceConstants.TEST_TIMEOUT_MS.toInt()).toLong()
                engine.startTest(timeout)
                result.success(null)
            }
            "cancelTest" -> {
                engine.cancelTest()
                result.success(null)
            }
            else -> result.notImplemented()
        }
    }

    override fun schedule(token: String, delayMs: Long) {
        posted.remove(token)?.let { handler.removeCallbacks(it) }
        val runnable = Runnable {
            posted.remove(token)
            engine.onScheduled(token)
        }
        posted[token] = runnable
        handler.postDelayed(runnable, delayMs)
    }

    override fun cancel(token: String) {
        posted.remove(token)?.let { handler.removeCallbacks(it) }
    }

    override fun onVoiceTrigger() {
        handler.post { channel.invokeMethod("onVoiceTrigger", null) }
    }

    override fun onLearnCaptured(
        keyCode: Int,
        scanCode: Int,
        androidKeyName: String?,
        gesture: String,
    ) {
        handler.post {
            channel.invokeMethod(
                "onLearnResult",
                mapOf(
                    "status" to "captured",
                    "keyCode" to keyCode,
                    "scanCode" to scanCode,
                    "androidKeyName" to androidKeyName,
                    "gesture" to gesture,
                    "label" to HardwareVoiceKeyPolicy.displayLabel(keyCode, androidKeyName),
                ),
            )
        }
    }

    override fun onLearnRejected(keyCode: Int, message: String) {
        handler.post {
            channel.invokeMethod(
                "onLearnResult",
                mapOf(
                    "status" to "rejected",
                    "keyCode" to keyCode,
                    "message" to message,
                ),
            )
        }
    }

    override fun onLearnTimeout() {
        handler.post {
            channel.invokeMethod("onLearnResult", mapOf("status" to "timeout"))
        }
    }

    override fun onLearnCancelled() {
        handler.post {
            channel.invokeMethod("onLearnResult", mapOf("status" to "cancelled"))
        }
    }

    override fun onTestRecognized() {
        handler.post {
            channel.invokeMethod("onTestResult", mapOf("status" to "recognized"))
        }
    }

    override fun onTestTimeout() {
        handler.post {
            channel.invokeMethod("onTestResult", mapOf("status" to "timeout"))
        }
    }

    override fun onTestCancelled() {
        handler.post {
            channel.invokeMethod("onTestResult", mapOf("status" to "cancelled"))
        }
    }

    override fun raiseVolume() {
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        audio.adjustSuggestedStreamVolume(
            AudioManager.ADJUST_RAISE,
            AudioManager.USE_DEFAULT_STREAM_TYPE,
            AudioManager.FLAG_SHOW_UI,
        )
    }
}
