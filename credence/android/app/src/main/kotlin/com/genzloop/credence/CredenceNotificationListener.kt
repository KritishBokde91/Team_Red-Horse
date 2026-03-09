package com.genzloop.credence

import android.content.SharedPreferences
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.ConcurrentHashMap

/**
 * CredenceNotificationListener — Listens to Android system notifications,
 * filters for WhatsApp messages, classifies them via LLM /classify API,
 * and triggers the overlay for news claims.
 *
 * Supports CONCURRENT verifications — multiple news claims can be
 * fact-checked simultaneously with stacked overlays.
 *
 * SAFETY: This reads Android OS-level notifications only.
 * WhatsApp has zero visibility into this service.
 */
class CredenceNotificationListener : NotificationListenerService() {

    companion object {
        private const val TAG = "CredenceNL"
        private const val WHATSAPP_PKG = "com.whatsapp"
        private const val WHATSAPP_BIZ_PKG = "com.whatsapp.w4b"
        private const val PREF_NAME = "credence_shield"
        private const val KEY_ENABLED = "shield_enabled"
        private const val KEY_API_URL = "api_url"
        private const val DEFAULT_API_URL = "http://localhost:8080"
        private const val DEBOUNCE_MS = 15000L
        private const val MAX_CONCURRENT = 3  // Max concurrent verifications
    }

    // Track recently processed messages (hash → timestamp)
    private val recentMessages = ConcurrentHashMap<Int, Long>()

    // Count active verification threads
    private var activeCount = 0
    private val activeCountLock = Any()

    private val prefs: SharedPreferences by lazy {
        getSharedPreferences(PREF_NAME, MODE_PRIVATE)
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        sbn ?: return

        // Only process WhatsApp notifications
        val pkg = sbn.packageName
        if (pkg != WHATSAPP_PKG && pkg != WHATSAPP_BIZ_PKG) return

        // Check if shield is enabled
        if (!prefs.getBoolean(KEY_ENABLED, false)) return

        // Extract notification text
        val extras = sbn.notification?.extras ?: return
        val text = extras.getCharSequence("android.text")?.toString()
            ?: extras.getCharSequence("android.bigText")?.toString()
            ?: return

        // Quick length filter (< 30 chars can't be news)
        if (text.length < 30) {
            Log.d(TAG, "Skipped (too short): ${text.take(30)}")
            return
        }

        // Debounce: skip if same message was processed recently
        val hash = text.hashCode()
        val now = System.currentTimeMillis()
        val lastTime = recentMessages[hash]
        if (lastTime != null && (now - lastTime) < DEBOUNCE_MS) {
            return
        }
        recentMessages[hash] = now

        // Clean up old entries from debounce map
        recentMessages.entries.removeIf { now - it.value > 60000 }

        // Check concurrent limit
        synchronized(activeCountLock) {
            if (activeCount >= MAX_CONCURRENT) {
                Log.w(TAG, "Max concurrent verifications ($MAX_CONCURRENT) reached, skipping")
                return
            }
            activeCount++
        }

        Log.d(TAG, "WhatsApp notification: ${text.take(60)}...")

        val apiUrl = prefs.getString(KEY_API_URL, DEFAULT_API_URL) ?: DEFAULT_API_URL

        // Call /classify API in background thread
        Thread {
            try {
                val isNews = classifyMessage(text, apiUrl)
                if (isNews) {
                    Log.i(TAG, "NEWS DETECTED by LLM — triggering overlay")
                    OverlayService.show(this, text, apiUrl)
                } else {
                    Log.d(TAG, "Skipped (not news per LLM)")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Classification failed", e)
            } finally {
                synchronized(activeCountLock) {
                    activeCount--
                }
            }
        }.start()
    }

    /**
     * Calls the /classify LLM endpoint to determine if a message
     * is a verifiable news claim or just regular chat/spam.
     */
    private fun classifyMessage(message: String, apiUrl: String): Boolean {
        val url = URL("$apiUrl/classify")
        val conn = url.openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.setRequestProperty("Content-Type", "application/json")
        conn.doOutput = true
        conn.connectTimeout = 10000
        conn.readTimeout = 60000

        val body = JSONObject().apply { put("message", message) }
        conn.outputStream.use { it.write(body.toString().toByteArray()) }

        if (conn.responseCode != 200) {
            Log.e(TAG, "Classify API returned ${conn.responseCode}")
            conn.disconnect()
            return false
        }

        val response = BufferedReader(InputStreamReader(conn.inputStream)).use { it.readText() }
        conn.disconnect()

        val json = JSONObject(response)
        val isNews = json.optBoolean("is_news", false)
        val confidence = json.optDouble("confidence", 0.0)
        val reason = json.optString("reason", "unknown")

        Log.i(TAG, "Classify: is_news=$isNews, conf=$confidence, reason=$reason")

        // Only trigger if LLM is > 60% confident it's news
        return isNews && confidence > 0.6
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {
        // No action needed
    }
}
