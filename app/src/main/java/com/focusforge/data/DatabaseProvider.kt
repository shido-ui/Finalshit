package com.focusforge.data

import android.content.Context
import androidx.room.Room
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

object DatabaseProvider {
    private val MIGRATION_1_2 = object : Migration(1, 2) {
        override fun migrate(database: SupportSQLiteDatabase) {
            database.execSQL(
                "CREATE TABLE IF NOT EXISTS library_items (" +
                    "id TEXT NOT NULL PRIMARY KEY, " +
                    "documentId TEXT NOT NULL, " +
                    "title TEXT NOT NULL, " +
                    "pinned INTEGER NOT NULL, " +
                    "archived INTEGER NOT NULL, " +
                    "fastModeEnabled INTEGER NOT NULL, " +
                    "createdAt INTEGER NOT NULL, " +
                    "updatedAt INTEGER NOT NULL)"
            )
            database.execSQL(
                "CREATE INDEX IF NOT EXISTS index_library_items_documentId " +
                    "ON library_items(documentId)"
            )
        }
    }

    fun create(context: Context): FocusForgeDatabase =
        Room.databaseBuilder(
            context,
            FocusForgeDatabase::class.java,
            "focusforge.db"
        ).addMigrations(MIGRATION_1_2).build()
}
