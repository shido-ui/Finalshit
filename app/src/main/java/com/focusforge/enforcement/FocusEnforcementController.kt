package com.focusforge.enforcement

import android.app.Activity
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context

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

    fun status(): EnforcementStatus {
        val owner = devicePolicyManager.isDeviceOwnerApp(appContext.packageName)
        return EnforcementStatus(
            deviceOwner = owner,
            lockTaskSupported = owner
        )
    }

    fun configureAllowedPackages(allowedPackages: Set<String>): Boolean {
        if (!devicePolicyManager.isDeviceOwnerApp(appContext.packageName)) return false

        val packages = (allowedPackages + appContext.packageName).toTypedArray()
        devicePolicyManager.setLockTaskPackages(adminComponent, packages)
        return true
    }

    fun startLockTask(activity: Activity, allowedPackages: Set<String>): Boolean {
        if (!configureAllowedPackages(allowedPackages)) return false
        activity.startLockTask()
        return true
    }

    fun stopLockTask(activity: Activity) {
        if (devicePolicyManager.isLockTaskPermitted(appContext.packageName)) {
            activity.stopLockTask()
        }
    }
}
