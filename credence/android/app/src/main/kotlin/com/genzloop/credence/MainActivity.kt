package com.genzloop.credence

import android.content.ComponentName
import android.content.Intent
import android.os.Build
import android.provider.Settings
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val CHANNEL = "com.genzloop.credence/shield"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "isShieldEnabled" -> {
                    val prefs = getSharedPreferences("credence_shield", MODE_PRIVATE)
                    result.success(prefs.getBoolean("shield_enabled", false))
                }

                "setShieldEnabled" -> {
                    val enabled = call.argument<Boolean>("enabled") ?: false
                    val prefs = getSharedPreferences("credence_shield", MODE_PRIVATE)
                    prefs.edit().putBoolean("shield_enabled", enabled).apply()
                    result.success(true)
                }

                "setApiUrl" -> {
                    val url = call.argument<String>("url") ?: "http://localhost:8080"
                    val prefs = getSharedPreferences("credence_shield", MODE_PRIVATE)
                    prefs.edit().putString("api_url", url).apply()
                    result.success(true)
                }

                "hasOverlayPermission" -> {
                    result.success(
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M)
                            Settings.canDrawOverlays(this)
                        else true
                    )
                }

                "requestOverlayPermission" -> {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                        val intent = Intent(
                            Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                            android.net.Uri.parse("package:$packageName")
                        )
                        startActivityForResult(intent, 1234)
                    }
                    result.success(true)
                }

                "hasNotificationAccess" -> {
                    val enabledListeners = Settings.Secure.getString(
                        contentResolver,
                        "enabled_notification_listeners"
                    )
                    val component = ComponentName(this, CredenceNotificationListener::class.java)
                    result.success(enabledListeners?.contains(component.flattenToString()) == true)
                }

                "requestNotificationAccess" -> {
                    val intent = Intent("android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS")
                    startActivity(intent)
                    result.success(true)
                }

                else -> result.notImplemented()
            }
        }
    }
}
