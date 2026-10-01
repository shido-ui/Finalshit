package com.focusforge.usage

import android.content.Context
import android.content.Intent
import android.provider.Settings

fun Context.openUsageAccessSettings() {
    startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
}
