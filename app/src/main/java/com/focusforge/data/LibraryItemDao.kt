package com.focusforge.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface LibraryItemDao {
    @Query(
        "SELECT * FROM library_items " +
            "WHERE archived = 0 ORDER BY pinned DESC, updatedAt DESC"
    )
    fun observeActive(): Flow<List<LibraryItem>>

    @Query("SELECT * FROM library_items WHERE documentId = :documentId LIMIT 1")
    suspend fun findByDocument(documentId: String): LibraryItem?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(item: LibraryItem)

    @Query(
        "UPDATE library_items SET pinned = :pinned, updatedAt = :updatedAt " +
            "WHERE documentId = :documentId"
    )
    suspend fun setPinned(documentId: String, pinned: Boolean, updatedAt: Long)

    @Query(
        "UPDATE library_items SET archived = :archived, updatedAt = :updatedAt " +
            "WHERE documentId = :documentId"
    )
    suspend fun setArchived(documentId: String, archived: Boolean, updatedAt: Long)

    @Query(
        "UPDATE library_items SET fastModeEnabled = :enabled, updatedAt = :updatedAt " +
            "WHERE documentId = :documentId"
    )
    suspend fun setFastMode(documentId: String, enabled: Boolean, updatedAt: Long)
}
