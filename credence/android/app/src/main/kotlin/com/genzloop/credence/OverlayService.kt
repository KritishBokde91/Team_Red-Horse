package com.genzloop.credence

import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.WindowManager
import android.widget.ImageView
import android.widget.TextView
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

/**
 * OverlayService — Draws a floating popup overlay (like Truecaller)
 * to show fact-check verdicts on top of WhatsApp.
 */
class OverlayService : Service() {

    private var windowManager: WindowManager? = null
    private var overlayView: View? = null
    private val handler = Handler(Looper.getMainLooper())
    private var dismissRunnable: Runnable? = null

    companion object {
        private const val TAG = "OverlayService"
        const val EXTRA_CLAIM = "claim"
        const val EXTRA_API_URL = "api_url"

        fun show(context: Context, claim: String, apiUrl: String) {
            val intent = Intent(context, OverlayService::class.java).apply {
                putExtra(EXTRA_CLAIM, claim)
                putExtra(EXTRA_API_URL, apiUrl)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val claim = intent?.getStringExtra(EXTRA_CLAIM) ?: return START_NOT_STICKY
        val apiUrl = intent.getStringExtra(EXTRA_API_URL) ?: "http://localhost:8080"

        Log.i(TAG, "Starting overlay for claim: ${claim.take(60)}...")
        Log.i(TAG, "API URL: $apiUrl")

        // Create foreground notification
        createForegroundNotification()

        // Show "Checking..." overlay immediately
        showOverlay(claim, "CHECKING", "Analyzing claim with AI...", -1.0)

        // Run verification in background thread
        Thread {
            try {
                Log.i(TAG, "Starting SSE verification request...")
                val result = verifyClaim(claim, apiUrl)
                val verdict = result.optString("verdict", "UNVERIFIED")
                val explanation = result.optString("explanation", "Could not verify")
                val score = result.optDouble("veracity_score", 0.0)
                Log.i(TAG, "Verdict received: $verdict (score=$score)")
                handler.post {
                    updateOverlay(claim, verdict, explanation, score)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Verification failed", e)
                handler.post {
                    updateOverlay(claim, "ERROR", "Check failed: ${e.message}", -1.0)
                }
            }
        }.start()

        return START_NOT_STICKY
    }

    private fun createForegroundNotification() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channelId = "credence_overlay"
            val channel = android.app.NotificationChannel(
                channelId,
                "Credence Fact-Check",
                android.app.NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Shows fact-check results"
                setShowBadge(false)
            }
            val nm = getSystemService(android.app.NotificationManager::class.java)
            nm.createNotificationChannel(channel)

            val notification = android.app.Notification.Builder(this, channelId)
                .setContentTitle("Credence Shield Active")
                .setContentText("Verifying news claim...")
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setOngoing(true)
                .build()
            startForeground(1001, notification)
        }
    }

    private fun showOverlay(claim: String, verdict: String, explanation: String, score: Double) {
        if (overlayView != null) removeOverlay()

        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        overlayView = LayoutInflater.from(this).inflate(R.layout.overlay_popup, null)

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            else
                @Suppress("DEPRECATION")
                WindowManager.LayoutParams.TYPE_SYSTEM_ALERT,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
            y = 100
        }

        populateOverlay(claim, verdict, explanation, score)
        windowManager?.addView(overlayView, params)
    }

    private fun updateOverlay(claim: String, verdict: String, explanation: String, score: Double) {
        if (overlayView == null) {
            showOverlay(claim, verdict, explanation, score)
            return
        }
        populateOverlay(claim, verdict, explanation, score)

        // Auto-dismiss after 15 seconds ONLY for final verdicts (not "CHECKING")
        if (verdict != "CHECKING") {
            dismissRunnable?.let { handler.removeCallbacks(it) }
            dismissRunnable = Runnable { removeOverlay(); stopSelf() }
            handler.postDelayed(dismissRunnable!!, 15000)
        }
    }

    private fun populateOverlay(claim: String, verdict: String, explanation: String, score: Double) {
        val view = overlayView ?: return

        val tvVerdict = view.findViewById<TextView>(R.id.tv_verdict)
        val tvClaim = view.findViewById<TextView>(R.id.tv_claim)
        val tvExplanation = view.findViewById<TextView>(R.id.tv_explanation)
        val tvScore = view.findViewById<TextView>(R.id.tv_score)
        val ivClose = view.findViewById<ImageView>(R.id.iv_close)
        val vIndicator = view.findViewById<View>(R.id.v_indicator)

        tvVerdict.text = verdict
        tvClaim.text = if (claim.length > 80) claim.take(80) + "..." else claim
        tvExplanation.text = if (explanation.length > 200) explanation.take(200) + "..." else explanation

        when (verdict) {
            "FAKE" -> {
                tvVerdict.setTextColor(0xFFEF4444.toInt())
                vIndicator.setBackgroundColor(0xFFEF4444.toInt())
                tvScore.text = "🔴 FAKE"
            }
            "TRUE" -> {
                tvVerdict.setTextColor(0xFF22C55E.toInt())
                vIndicator.setBackgroundColor(0xFF22C55E.toInt())
                tvScore.text = "🟢 TRUE"
            }
            "CHECKING" -> {
                tvVerdict.setTextColor(0xFF78716C.toInt())
                vIndicator.setBackgroundColor(0xFF78716C.toInt())
                tvScore.text = "⏳ Checking..."
            }
            "ERROR" -> {
                tvVerdict.setTextColor(0xFFEF4444.toInt())
                vIndicator.setBackgroundColor(0xFFEF4444.toInt())
                tvScore.text = "⚠️ Error"
            }
            else -> {
                tvVerdict.setTextColor(0xFFF59E0B.toInt())
                vIndicator.setBackgroundColor(0xFFF59E0B.toInt())
                tvScore.text = "🟡 UNVERIFIED"
            }
        }

        ivClose.setOnClickListener {
            removeOverlay()
            stopSelf()
        }
    }

    private fun removeOverlay() {
        overlayView?.let {
            try { windowManager?.removeView(it) } catch (_: Exception) {}
        }
        overlayView = null
    }

    /**
     * Calls the /verify endpoint with SSE (Server-Sent Events) and
     * extracts the final verdict. Reads the entire byte stream line-by-line.
     */
    private fun verifyClaim(claim: String, apiUrl: String): JSONObject {
        val url = URL("$apiUrl/verify")
        Log.d(TAG, "Connecting to: $url")

        val conn = url.openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.setRequestProperty("Content-Type", "application/json")
        conn.setRequestProperty("Accept", "text/event-stream")
        conn.setRequestProperty("Cache-Control", "no-cache")
        conn.doOutput = true
        conn.connectTimeout = 15000       // 15s to connect
        conn.readTimeout = 300000         // 5 minutes for full pipeline

        val body = JSONObject().apply { put("claim", claim) }
        conn.outputStream.use { it.write(body.toString().toByteArray()) }

        val responseCode = conn.responseCode
        Log.d(TAG, "HTTP response code: $responseCode")

        if (responseCode != 200) {
            val errorBody = try {
                conn.errorStream?.bufferedReader()?.readText() ?: "No error body"
            } catch (_: Exception) { "Could not read error" }
            Log.e(TAG, "HTTP error $responseCode: $errorBody")
            conn.disconnect()
            return JSONObject().apply {
                put("verdict", "ERROR")
                put("explanation", "Server returned HTTP $responseCode")
                put("veracity_score", 0.0)
            }
        }

        val reader = BufferedReader(InputStreamReader(conn.inputStream, "UTF-8"))
        var verdictJson = JSONObject().apply {
            put("verdict", "UNVERIFIED")
            put("explanation", "Pipeline did not return a verdict")
            put("veracity_score", 0.0)
        }

        try {
            var line: String? = reader.readLine()
            while (line != null) {
                Log.d(TAG, "SSE: $line")

                if (line.startsWith("data: ")) {
                    val payload = line.substring(6).trim()
                    if (payload == "[DONE]") {
                        Log.i(TAG, "Received [DONE] signal")
                        break
                    }

                    try {
                        val event = JSONObject(payload)
                        val type = event.optString("type", "")

                        // Update overlay with stage progress
                        if (type == "stage") {
                            val msg = event.optString("message", "Processing...")
                            handler.post { updateOverlay(claim, "CHECKING", msg, -1.0) }
                        }

                        // Capture final verdict
                        if (type == "verdict") {
                            verdictJson = event
                            Log.i(TAG, "VERDICT CAPTURED: ${event.optString("verdict")}")
                        }
                    } catch (e: Exception) {
                        Log.w(TAG, "JSON parse error for SSE line: ${e.message}")
                    }
                }

                line = reader.readLine()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error reading SSE stream", e)
        } finally {
            try { reader.close() } catch (_: Exception) {}
            conn.disconnect()
        }

        return verdictJson
    }

    override fun onDestroy() {
        removeOverlay()
        dismissRunnable?.let { handler.removeCallbacks(it) }
        super.onDestroy()
    }
}
