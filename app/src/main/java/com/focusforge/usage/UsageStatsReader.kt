package com.focusforge.usage

import android.app.usage.UsageStatsManager
import android.content.Context

data class AppUsage(
    val packageName: String,
    val totalTimeMs: Long
)

class UsageStatsReader(context: Context) {
    private val usageStatsManager =
        context.getSystemService(UsageStatsManager::class.java)

    fun todayUsage(nowMs: Long = System.currentTimeMillis()): List<AppUsage> {
        val start = nowMs - 24L * 60L * 60L * 1000L
        return usageStatsManager
            .queryUsageStats(UsageStatsManager.INTERVAL_DAILY, start, nowMs)
            .asSequence()
            .filter { it.totalTimeInForeground > 0L }
            .map { AppUsage(it.packageName, it.totalTimeInForeground) }
            .sortedByDescending { it.totalTimeMs }
            .toList()
    }
}
