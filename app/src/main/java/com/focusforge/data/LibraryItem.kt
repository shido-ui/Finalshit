package com.focusforge.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "library_items")
data class LibraryItem(
    @PrimaryKey val id: String,
    val documentId: String,
    val title: String,
    val pinned: Boolean = false,
    val archived: Boolean = false,
    val fastModeEnabled: Boolean = true,
    val createdAt: Long,
    val updatedAt: Long
)
