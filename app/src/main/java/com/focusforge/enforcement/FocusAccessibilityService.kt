package com.focusforge.enforcement

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.view.accessibility.AccessibilityEvent
import androidx.datastore.preferences.core.stringSetPreferencesKey
import com.focusforge.FocusForgeApplication
import com.focusforge.data.focusForgePreferences
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.cancel

class FocusAccessibilityService : AccessibilityService() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        val packageName = event?.packageName?.toString() ?: return
        if (packageName == applicationContext.packageName) return

        scope.launch {
            val app = applicationContext as FocusForgeApplication
            val session = app.sessionRepository.activeSession.first() ?: return@launch
            val key = stringSetPreferencesKey("allowed_packages")
            val allowed = applicationContext.focusForgePreferences.data.first()[key].orEmpty() +
                applicationContext.packageName

            if (packageName !in allowed) {
                val intent = Intent(applicationContext, com.focusforge.MainActivity::class.java).apply {
                    addFlags(
                        Intent.FLAG_ACTIVITY_NEW_TASK or
                            Intent.FLAG_ACTIVITY_CLEAR_TOP or
                            Intent.FLAG_ACTIVITY_SINGLE_TOP
                    )
                    putExtra("focus_blocked_package", packageName)
                }
                startActivity(intent)
            }
        }
    }

    override fun onInterrupt() = Unit

    override fun onDestroy() {
        scope.coroutineContext.cancel()
        super.onDestroy()
    }
}
