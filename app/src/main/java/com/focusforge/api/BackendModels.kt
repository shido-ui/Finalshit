package com.focusforge.api

data class BackendDocument(
    val id: String,
    val filename: String,
    val pageCount: Int,
    val status: String,
    val error: String?,
    val questionCount: Int
)

data class BackendLibraryItem(
    val documentId: String,
    val title: String,
    val pinned: Boolean,
    val archived: Boolean,
    val fastModeEnabled: Boolean
)

data class BackendHealth(
    val status: String,
    val service: String
)

data class PracticeQuestion(
    val id: String,
    val position: Int,
    val text: String,
    val options: Map<String, String>,
    val taxonomyNodeId: String?,
    val difficulty: String?,
    val hasDiagram: Boolean,
    val hasTable: Boolean
)

data class PracticeSession(
    val id: String,
    val mode: String,
    val questionIds: List<String>,
    val startedAt: String,
    val submittedAt: String?,
    val score: Int?,
    val total: Int,
    val answered: Int
)

data class PracticeStart(
    val session: PracticeSession,
    val questions: List<PracticeQuestion>
)

data class PracticeResult(
    val sessionId: String,
    val score: Int,
    val total: Int,
    val answered: Int,
    val correct: Int,
    val percentage: Double,
    val questionResults: Map<String, Boolean>
)


data class WeaknessProfile(
    val taxonomyNodeId: String,
    val attempts: Int,
    val correct: Int,
    val incorrect: Int,
    val accuracy: Double,
    val mastery: Double,
    val lastAttemptAt: String?
)

data class ReviewState(
    val questionId: String,
    val repetitions: Int,
    val intervalDays: Int,
    val easeFactor: Double,
    val dueAt: String,
    val lastReviewedAt: String?,
    val lastCorrect: Boolean?
)


data class CopilotAnswer(
    val answer: String,
    val citations: List<Int>,
    val confidence: Double,
    val evidence: String
)
