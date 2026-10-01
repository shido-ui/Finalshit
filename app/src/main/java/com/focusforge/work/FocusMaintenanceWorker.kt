package com.focusforge.work

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.focusforge.FocusForgeApplication

class FocusMaintenanceWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        return runCatching {
            val app = applicationContext as FocusForgeApplication
            app.sessionRepository.recoverExpiredIfExpired(System.currentTimeMillis())
            Result.success()
        }.getOrElse {
            Result.retry()
        }
    }
}
