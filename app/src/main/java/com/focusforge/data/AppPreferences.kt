package com.focusforge.data

import android.content.Context
import androidx.datastore.preferences.preferencesDataStore

val Context.focusForgePreferences by preferencesDataStore(name = "focusforge_preferences")
