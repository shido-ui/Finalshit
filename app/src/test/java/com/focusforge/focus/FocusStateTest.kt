package com.focusforge.focus

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FocusStateTest {
    @Test
    fun stateMachine_contains_expected_states() {
        assertTrue(FocusState.entries.map { it.name }.containsAll(
            listOf("IDLE", "ARMED", "LOCKED", "ENDING")
        ))
    }

    @Test
    fun stateMachine_accepts_only_supported_transitions() {
        assertTrue(FocusStateMachine.canTransition(FocusState.IDLE, FocusState.ARMED))
        assertTrue(FocusStateMachine.canTransition(FocusState.ARMED, FocusState.LOCKED))
        assertTrue(FocusStateMachine.canTransition(FocusState.ARMED, FocusState.IDLE))
        assertTrue(FocusStateMachine.canTransition(FocusState.LOCKED, FocusState.ENDING))
        assertTrue(FocusStateMachine.canTransition(FocusState.ENDING, FocusState.IDLE))

        assertFalse(FocusStateMachine.canTransition(FocusState.IDLE, FocusState.LOCKED))
        assertFalse(FocusStateMachine.canTransition(FocusState.LOCKED, FocusState.IDLE))
        assertFalse(FocusStateMachine.canTransition(FocusState.ENDING, FocusState.LOCKED))
    }
}
