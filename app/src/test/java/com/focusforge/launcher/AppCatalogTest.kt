package com.focusforge.launcher

import org.junit.Assert.assertEquals
import org.junit.Test

class AppCatalogTest {
    @Test
    fun launchableApp_model_preserves_package_and_label() {
        val app = LaunchableApp("com.example.study", "Study")
        assertEquals("com.example.study", app.packageName)
        assertEquals("Study", app.label)
    }
}
