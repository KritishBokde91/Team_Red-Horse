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
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger
import org.json.JSONObject

/**
 * OverlayService — Draws floating popup overlays with fact-check verdicts.
 *
 * Supports CONCURRENT verifications:
 * - Each incoming claim gets its own background thread + overlay
 * - Multiple overlays stack vertically
 * - Each overlay streams live pipeline stage progress
 * - User can dismiss any individual overlay
 */
class OverlayService : Service() {

    private var windowManager: WindowManager? = null
    private val handler = Handler(Looper.getMainLooper())

    // Track active jobs — each has its own overlay and thread
    private val activeJobs = ConcurrentHashMap<Int, JobState>()
    private val jobCounter = AtomicInteger(0)

    data class JobState(
        val jobId: Int,
        val claim: String,
        var overlayView: View? = null,
        var thread: Thread? = null,
        var dismissRunnable: Runnable? = null,
    )

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

        // Create foreground notification (only once)
        if (activeJobs.isEmpty()) {
            createForegroundNotification()
        }

        val jobId = jobCounter.incrementAndGet()
        Log.i(TAG, "Job #$jobId starting: ${claim.take(50)}...")

        val job = JobState(jobId, claim)
        activeJobs[jobId] = job

        // Show "Checking..." overlay immediately
        handler.post { showOverlayForJob(job, "CHECKING", "⏳ Analyzing claim with AI...", -1.0) }

        // Run verification in background thread
        job.thread = Thread {
            try {
                val result = verifyClaim(jobId, claim, apiUrl)
                val verdict = result.optString("verdict", "UNVERIFIED")
                val explanation = result.optString("explanation", "Could not verify")
                val score = result.optDouble("veracity_score", 0.0)
                Log.i(TAG, "Job #$jobId verdict: $verdict (score=$score)")
                handler.post {
                    updateOverlayForJob(jobId, verdict, explanation, score)
                    // Auto-dismiss after 20 seconds
                    scheduleAutoDismiss(jobId, 20000)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Job #$jobId failed", e)
                handler.post {
                    updateOverlayForJob(jobId, "ERROR", "Check failed: ${e.message}", -1.0)
                    scheduleAutoDismiss(jobId, 10000)
                }
            }
        }.also { it.start() }

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
                .setContentText("Monitoring for misinformation...")
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setOngoing(true)
                .build()
            startForeground(1001, notification)
        }
    }

    /**
     * Calculate Y offset for stacking overlays vertically.
     */
    private fun getYOffset(jobId: Int): Int {
        val index = activeJobs.keys.sorted().indexOf(jobId)
        return 80 + (index * 460) // Stack overlays with 460px gap
    }

    private fun showOverlayForJob(job: JobState, verdict: String, explanation: String, score: Double) {
        if (windowManager == null) {
            windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        }

        val view = LayoutInflater.from(this).inflate(R.layout.overlay_popup, null)
        job.overlayView = view

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
            y = getYOffset(job.jobId)
        }

        populateOverlay(view, job.claim, verdict, explanation, score)
        windowManager?.addView(view, params)
    }

    private fun updateOverlayForJob(jobId: Int, verdict: String, explanation: String, score: Double) {
        val job = activeJobs[jobId] ?: return
        val view = job.overlayView ?: return
        populateOverlay(view, job.claim, verdict, explanation, score)
    }

    private fun populateOverlay(view: View, claim: String, verdict: String, explanation: String, score: Double) {
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

        // Find the jobId for this view so we can dismiss it
        val jobId = activeJobs.entries.find { it.value.overlayView == view }?.key
        ivClose.setOnClickListener {
            if (jobId != null) dismissJob(jobId)
        }
    }

    private fun scheduleAutoDismiss(jobId: Int, delayMs: Long) {
        val job = activeJobs[jobId] ?: return
        job.dismissRunnable?.let { handler.removeCallbacks(it) }
        job.dismissRunnable = Runnable { dismissJob(jobId) }
        handler.postDelayed(job.dismissRunnable!!, delayMs)
    }

    private fun dismissJob(jobId: Int) {
        val job = activeJobs.remove(jobId) ?: return
        Log.i(TAG, "Dismissing job #$jobId")

        // Remove overlay
        job.overlayView?.let {
            try { windowManager?.removeView(it) } catch (_: Exception) {}
        }
        job.overlayView = null

        // Cancel dismiss timer
        job.dismissRunnable?.let { handler.removeCallbacks(it) }

        // Interrupt thread if still running
        job.thread?.interrupt()

        // Stop service if no more active jobs
        if (activeJobs.isEmpty()) {
            stopSelf()
        }
    }

    /**
     * Calls the /verify endpoint with SSE and extracts the verdict.
     * Streams live stage updates to the overlay.
     */
    private fun verifyClaim(jobId: Int, claim: String, apiUrl: String): JSONObject {
        val url = URL("$apiUrl/verify")
        Log.d(TAG, "Job #$jobId connecting to: $url")

        val conn = url.openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.setRequestProperty("Content-Type", "application/json")
        conn.setRequestProperty("Accept", "text/event-stream")
        conn.setRequestProperty("Cache-Control", "no-cache")
        conn.setRequestProperty("Connection", "keep-alive")
        conn.doOutput = true
        conn.connectTimeout = 15000
        conn.readTimeout = 300000

        val body = JSONObject().apply { put("claim", claim) }
        conn.outputStream.use { it.write(body.toString().toByteArray()) }

        val responseCode = conn.responseCode
        Log.d(TAG, "Job #$jobId HTTP: $responseCode")

        if (responseCode != 200) {
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

        // Stage emoji mapping for streaming display
        val stageEmoji = mapOf(
            "claim_extraction" to "🔍 Extracting claims...",
            "multi_tier_search" to "🌐 Searching fact-check databases...",
            "scraping" to "📄 Reading evidence pages...",
            "stance_detection" to "⚖️ Analyzing evidence stance...",
            "verdict" to "🧮 Computing verdict...",
            "explanation" to "📝 Generating explanation...",
        )

        try {
            var line: String? = reader.readLine()
            while (line != null && !Thread.currentThread().isInterrupted) {
                if (line.startsWith("data: ")) {
                    val payload = line.substring(6).trim()
                    if (payload == "[DONE]") break

                    try {
                        val event = JSONObject(payload)
                        val type = event.optString("type", "")

                        // Stream stage updates to the overlay
                        when (type) {
                            "stage" -> {
                                val stage = event.optString("stage", "")
                                val stageMsg = stageEmoji[stage] ?: event.optString("message", "Processing...")
                                handler.post { updateOverlayForJob(jobId, "CHECKING", stageMsg, -1.0) }
                            }
                            "tier_searching" -> {
                                val tierName = event.optString("tier_name", "")
                                handler.post { updateOverlayForJob(jobId, "CHECKING", "🔎 Searching: $tierName", -1.0) }
                            }
                            "scraping_evidence" -> {
                                val idx = event.optInt("index", 0)
                                val total = event.optInt("total", 0)
                                handler.post { updateOverlayForJob(jobId, "CHECKING", "📄 Scraping evidence $idx/$total...", -1.0) }
                            }
                            "stance_result" -> {
                                val stance = event.optString("stance", "")
                                val stanceUrl = event.optString("url", "").let {
                                    if (it.length > 40) it.take(40) + "..." else it
                                }
                                handler.post { updateOverlayForJob(jobId, "CHECKING", "⚖️ $stance — $stanceUrl", -1.0) }
                            }
                            "verdict" -> {
                                verdictJson = event
                                Log.i(TAG, "Job #$jobId VERDICT: ${event.optString("verdict")}")
                            }
                        }
                    } catch (_: Exception) {}
                }
                line = reader.readLine()
            }
        } catch (e: Exception) {
            if (!Thread.currentThread().isInterrupted) {
                Log.w(TAG, "Job #$jobId SSE stream ended: ${e.message}")
            }
        } finally {
            try { reader.close() } catch (_: Exception) {}
            conn.disconnect()
        }

        return verdictJson
    }

    override fun onDestroy() {
        // Clean up all active jobs
        activeJobs.keys.toList().forEach { dismissJob(it) }
        super.onDestroy()
    }
}
