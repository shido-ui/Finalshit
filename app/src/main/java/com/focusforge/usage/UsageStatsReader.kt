package com.focusforge.usage

import android.app.usage.UsageStatsManager
import android.content.Context
import java.util.Calendar

data class AppUsage(
    val packageName: String,
    val totalTimeMs: Long
)

class UsageStatsReader(context: Context) {
    private val usageStatsManager =
        context.getSystemService(UsageStatsManager::class.java)

    fun todayUsage(nowMs: Long = System.currentTimeMillis()): List<AppUsage> {
        val calendar = Calendar.getInstance().apply {
            timeInMillis = nowMs
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val start = calendar.timeInMillis
        return usageStatsManager
            .queryUsageStats(UsageStatsManager.INTERVAL_DAILY, start, nowMs)
            .asSequence()
            .filter { it.totalTimeInForeground > 0L }
            .map { AppUsage(it.packageName, it.totalTimeInForeground) }
            .sortedByDescending { it.totalTimeMs }
            .toList()
    }
}
