package com.focusforge

import android.app.Application
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.focusforge.data.DatabaseProvider
import com.focusforge.data.LibraryRepository
import com.focusforge.focus.FocusSessionManager
import com.focusforge.focus.FocusSessionRepository
import com.focusforge.work.FocusMaintenanceWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import java.util.concurrent.TimeUnit

class FocusForgeApplication : Application() {
    private val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    lateinit var sessionManager: FocusSessionManager
        private set

    lateinit var libraryRepository: LibraryRepository
        private set

    override fun onCreate() {
        super.onCreate()

        val database = DatabaseProvider.create(this)
        val repository = FocusSessionRepository(database.focusSessionDao())
        libraryRepository = LibraryRepository(database.libraryItemDao())
        val workManager = WorkManager.getInstance(this)

        sessionManager = FocusSessionManager(
            repository = repository,
            workManager = workManager,
            scope = applicationScope
        )

        workManager.enqueueUniquePeriodicWork(
            "focus-maintenance",
            ExistingPeriodicWorkPolicy.KEEP,
            PeriodicWorkRequestBuilder<FocusMaintenanceWorker>(15, TimeUnit.MINUTES).build()
        )
    }
}
