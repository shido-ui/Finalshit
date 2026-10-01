package com.focusforge.data

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(entities = [FocusSession::class, LibraryItem::class], version = 2, exportSchema = false)
abstract class FocusForgeDatabase : RoomDatabase() {
    abstract fun focusSessionDao(): FocusSessionDao
    abstract fun libraryItemDao(): LibraryItemDao
}
