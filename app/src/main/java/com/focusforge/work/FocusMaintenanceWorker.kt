package com.focusforge.work

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.focusforge.data.DatabaseProvider
import com.focusforge.focus.FocusSessionRepository
import kotlinx.coroutines.flow.first

class FocusMaintenanceWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        return runCatching {
            val database = DatabaseProvider.create(applicationContext)
            val repository = FocusSessionRepository(database.focusSessionDao())
            val now = System.currentTimeMillis()

            repository.activeSession.first()?.let { session ->
                repository.recoverExpired(session, now)
            }

            database.close()
            Result.success()
        }.getOrElse {
            Result.retry()
        }
    }
}
