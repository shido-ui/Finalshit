package com.focusforge.focus

import org.junit.Assert.assertEquals
import org.junit.Test

class FocusStateTest {
    @Test
    fun stateMachine_contains_expected_states() {
        assertEquals(
            listOf("IDLE", "ARMED", "LOCKED", "ENDING"),
            FocusState.entries.map { it.name }
        )
    }
}
