package com.focusforge.api

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.delay

class BackendRepository(context: Context) {
    private val api = FocusForgeApi(context)

    suspend fun checkHealth(): BackendHealth = api.health()

    suspend fun importPdf(uri: Uri, filename: String): BackendDocument {
        var document = api.ingestPdf(uri, filename)
        repeat(300) {
            if (document.status == "ready" || document.status == "failed") return document
            delay(1000)
            document = api.getDocument(document.id)
        }
        return document
    }

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
    
    suspend fun getWeaknesses(limit: Int = 20): List<WeaknessProfile> =
        api.getWeaknesses(limit)

    suspend fun getDueReviewQuestionIds(limit: Int = 100): List<String> =
        api.getDueReviewQuestionIds(limit)

    suspend fun getReviewState(questionId: String): ReviewState =
        api.getReviewState(questionId)
}

