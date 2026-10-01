package com.focusforge.data

import kotlinx.coroutines.flow.Flow

class LibraryRepository(
    private val dao: LibraryItemDao
) {
    fun observeActive(): Flow<List<LibraryItem>> = dao.observeActive()

    suspend fun upsert(item: LibraryItem) = dao.upsert(item)

    suspend fun findByDocument(documentId: String): LibraryItem? = dao.findByDocument(documentId)

    suspend fun setPinned(documentId: String, pinned: Boolean) =
        dao.setPinned(documentId, pinned, System.currentTimeMillis())

    suspend fun setArchived(documentId: String, archived: Boolean) =
        dao.setArchived(documentId, archived, System.currentTimeMillis())

    suspend fun setFastMode(documentId: String, enabled: Boolean) =
        dao.setFastMode(documentId, enabled, System.currentTimeMillis())
}
