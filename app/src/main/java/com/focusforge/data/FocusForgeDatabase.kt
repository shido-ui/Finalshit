package com.focusforge.data

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(entities = [FocusSession::class], version = 1, exportSchema = false)
abstract class FocusForgeDatabase : RoomDatabase() {
    abstract fun focusSessionDao(): FocusSessionDao
}
