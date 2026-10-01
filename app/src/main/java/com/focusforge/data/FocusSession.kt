package com.focusforge.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "focus_sessions")
data class FocusSession(
    @PrimaryKey val id: String,
    val state: String,
    val startedAtEpochMs: Long?,
    val plannedDurationMs: Long,
    val updatedAtEpochMs: Long
)
