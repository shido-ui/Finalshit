package com.focusforge.focus

import com.focusforge.data.FocusSession
import com.focusforge.data.FocusSessionDao
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import java.util.UUID

class FocusSessionRepository(
    private val dao: FocusSessionDao
) {
    val sessions: Flow<List<FocusSession>> = dao.observeAll()

    val activeSession: Flow<FocusSession?> = sessions.map { items ->
        items.firstOrNull { it.state != FocusState.IDLE.name }
    }

    suspend fun createArmed(durationMs: Long, nowMs: Long): FocusSession {
        require(durationMs > 0) { "Focus duration must be positive" }
        val session = FocusSession(
            id = UUID.randomUUID().toString(),
            state = FocusState.ARMED.name,
            startedAtEpochMs = nowMs,
            plannedDurationMs = durationMs,
            updatedAtEpochMs = nowMs
        )
        dao.upsert(session)
        return session
    }

    suspend fun transition(
        session: FocusSession,
        to: FocusState,
        nowMs: Long
    ): FocusSession {
        val from = FocusState.valueOf(session.state)
        FocusStateMachine.requireTransition(from, to)
        val updated = session.copy(
            state = to.name,
            updatedAtEpochMs = nowMs
        )
        dao.upsert(updated)
        return updated
    }

    suspend fun recoverExpiredIfExpired(nowMs: Long): FocusSession? =
        activeSession.first()?.let { recoverExpired(it, nowMs) }

    suspend fun recoverExpired(session: FocusSession, nowMs: Long): FocusSession? {
        if (session.state != FocusState.LOCKED.name) return null
        val start = session.startedAtEpochMs ?: return null
        if (nowMs < start + session.plannedDurationMs) return null

        val ending = transition(session, FocusState.ENDING, nowMs)
        return transition(ending, FocusState.IDLE, nowMs)
    }
}
