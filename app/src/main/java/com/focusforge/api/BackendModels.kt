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
