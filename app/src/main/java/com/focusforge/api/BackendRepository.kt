package com.focusforge.api

import android.content.Context
import android.net.Uri

class BackendRepository(context: Context) {
    private val api = FocusForgeApi(context)

    suspend fun checkHealth(): BackendHealth = api.health()

    suspend fun importPdf(uri: Uri, filename: String): BackendDocument =
        api.ingestPdf(uri, filename)

    suspend fun syncLibrary(): List<BackendLibraryItem> = api.getLibrary()

    suspend fun updateLibrary(
        documentId: String,
        pinned: Boolean? = null,
        archived: Boolean? = null,
        fastModeEnabled: Boolean? = null
    ): BackendLibraryItem = api.updateLibrary(
        documentId, pinned, archived, fastModeEnabled
    )

    suspend fun startPractice(
        mode: String = "fast",
        limit: Int = 10,
        documentId: String? = null,
        taxonomyNodeId: String? = null
    ): PracticeStart = api.startPractice(mode, limit, documentId, taxonomyNodeId)

    suspend fun submitPractice(
        sessionId: String,
        answers: Map<String, String>
    ): PracticeResult = api.submitPractice(sessionId, answers)
}
