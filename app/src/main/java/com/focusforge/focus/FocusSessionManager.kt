package com.focusforge.focus

import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import com.focusforge.data.FocusSession
import com.focusforge.work.FocusMaintenanceWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import java.util.concurrent.TimeUnit

class FocusSessionManager(
    private val repository: FocusSessionRepository,
    private val workManager: WorkManager,
    private val scope: CoroutineScope,
    private val nowMs: () -> Long = { System.currentTimeMillis() }
) {
    private val _state = MutableStateFlow(FocusState.IDLE)
    val state: StateFlow<FocusState> = _state.asStateFlow()

    suspend fun start(durationMs: Long): Boolean {
        require(durationMs > 0)
        scope.launch {
            val existing = repository.activeSession.first()
            if (existing != null) {
                recoverOrFinish(existing)
                if (repository.activeSession.first() != null) return false
            }

            val armed = repository.createArmed(durationMs, nowMs())
            val locked = repository.transition(armed, FocusState.LOCKED, nowMs())
            _state.value = FocusState.LOCKED

            val request = OneTimeWorkRequestBuilder<FocusMaintenanceWorker>()
                .setInitialDelay(locked.plannedDurationMs, TimeUnit.MILLISECONDS)
                .build()
            workManager.enqueueUniqueWork(
                "focus-end-" + locked.id,
                ExistingWorkPolicy.REPLACE,
                request
            )
            return true
    }

    fun cancel() {
        scope.launch {
            val active = repository.activeSession.first() ?: run {
                _state.value = FocusState.IDLE
                return@launch
            }
            when (FocusState.valueOf(active.state)) {
                FocusState.ARMED -> repository.transition(active, FocusState.IDLE, nowMs())
                FocusState.LOCKED -> {
                    val ending = repository.transition(active, FocusState.ENDING, nowMs())
                    repository.transition(ending, FocusState.IDLE, nowMs())
                }
                else -> _state.value = FocusState.IDLE
            }
            _state.value = FocusState.IDLE
        }
    }

    suspend fun recover() {
        val active = repository.activeSession.first()
        if (active == null) {
            _state.value = FocusState.IDLE
            return
        }
        val current = FocusState.valueOf(active.state)
        if (current == FocusState.LOCKED && repository.recoverExpired(active, nowMs()) != null) {
            _state.value = FocusState.IDLE
            return
        }
        _state.value = current
    }

    private suspend fun recoverOrFinish(session: FocusSession) {
        when (FocusState.valueOf(session.state)) {
            FocusState.LOCKED -> repository.recoverExpired(session, nowMs())
            FocusState.ARMED -> repository.transition(session, FocusState.IDLE, nowMs())
            else -> Unit
        }
    }
}
