package com.focusforge.focus

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.focusforge.FocusForgeApplication
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.cancel

class FocusForegroundService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var ticker: Job? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        createChannel()
        startForeground(NOTIFICATION_ID, buildNotification("Focus session active"))
        ticker?.cancel()
        ticker = scope.launch {
            val repository = (application as FocusForgeApplication).sessionRepository
            while (isActive) {
                val session = repository.activeSession.first()
                if (session == null || session.state != FocusState.LOCKED.name) {
                    stopSelf()
                    break
                }
                val start = session.startedAtEpochMs ?: 0L
                val remaining = (start + session.plannedDurationMs - System.currentTimeMillis()).coerceAtLeast(0L)
                val minutes = remaining / 60_000L
                val seconds = (remaining / 1_000L) % 60L
                val notification = buildNotification(
                    "Focus active • %02d:%02d remaining".format(minutes, seconds)
                )
                getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification)
                delay(1_000L)
            }
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        ticker?.cancel()
        scope.coroutineContext.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                "Focus sessions",
                NotificationManager.IMPORTANCE_LOW
            )
        )
    }

    private fun buildNotification(text: String) =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
            .setContentTitle("FocusForge")
            .setContentText(text)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build()

    companion object {
        const val ACTION_START = "com.focusforge.action.START_FOCUS"
        const val ACTION_STOP = "com.focusforge.action.STOP_FOCUS"
        private const val CHANNEL_ID = "focus_sessions"
        private const val NOTIFICATION_ID = 1001
    }
}
