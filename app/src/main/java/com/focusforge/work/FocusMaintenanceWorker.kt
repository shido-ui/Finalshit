package com.focusforge.work

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters

class FocusMaintenanceWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result = Result.success()
}
