package com.focusforge.enforcement

import android.app.Activity
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.provider.Settings

data class EnforcementStatus(
    val deviceOwner: Boolean,
    val lockTaskSupported: Boolean
)

class FocusEnforcementController(context: Context) {
    private val appContext = context.applicationContext
    private val devicePolicyManager =
        appContext.getSystemService(DevicePolicyManager::class.java)
    private val adminComponent =
        ComponentName(appContext, FocusDeviceAdminReceiver::class.java)

    fun accessibilityEnabled(): Boolean {
        val enabled = Settings.Secure.getString(
            appContext.contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ).orEmpty()
        val expected = ComponentName(appContext, FocusAccessibilityService::class.java).flattenToString()
        return enabled.split(':').any { it.equals(expected, ignoreCase = true) }
    }

    fun openAccessibilitySettings(activity: Activity) {
        activity.startActivity(android.content.Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
    }

    fun status(): EnforcementStatus {
        val owner = devicePolicyManager.isDeviceOwnerApp(appContext.packageName)
        val permitted = try {
            devicePolicyManager.isLockTaskPermitted(appContext.packageName)
        } catch (_: SecurityException) {
            false
        }
        return EnforcementStatus(
            deviceOwner = owner,
            lockTaskSupported = owner && permitted
        )
    }

    fun configureAllowedPackages(allowedPackages: Set<String>): Boolean {
        if (!devicePolicyManager.isDeviceOwnerApp(appContext.packageName)) return false

        val packages = (allowedPackages + appContext.packageName).toTypedArray()
        return try {
            devicePolicyManager.setLockTaskPackages(adminComponent, packages)
            true
        } catch (_: SecurityException) {
            false
        } catch (_: IllegalArgumentException) {
            false
        }
    }

    fun startLockTask(activity: Activity, allowedPackages: Set<String>): Boolean {
        if (!devicePolicyManager.isDeviceOwnerApp(appContext.packageName)) return false
        if (!configureAllowedPackages(allowedPackages)) return false
        if (!status().lockTaskSupported) return false
        return try {
            activity.startLockTask()
            true
        } catch (_: SecurityException) {
            false
        } catch (_: IllegalStateException) {
            false
        }
    }

    fun stopLockTask(activity: Activity) {
        if (!devicePolicyManager.isDeviceOwnerApp(appContext.packageName)) return
        try {
            activity.stopLockTask()
        } catch (_: SecurityException) {
            // The focus session can still be cancelled if enforcement is no longer active.
        } catch (_: IllegalStateException) {
            // Activity may already have left lock-task mode.
        }
    }
}
