package com.focusforge.data

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

@Dao
interface FocusSessionDao {
    @Upsert suspend fun upsert(session: FocusSession)
    @Query("SELECT * FROM focus_sessions ORDER BY updatedAtEpochMs DESC")
    fun observeAll(): Flow<List<FocusSession>>
}
