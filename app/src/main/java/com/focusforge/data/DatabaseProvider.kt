package com.focusforge.data

import android.content.Context
import androidx.room.Room

object DatabaseProvider {
    fun create(context: Context): FocusForgeDatabase =
        Room.databaseBuilder(
            context,
            FocusForgeDatabase::class.java,
            "focusforge.db"
        ).build()
}
