package com.focusforge.focus

object FocusStateMachine {
    fun canTransition(from: FocusState, to: FocusState): Boolean = when (from) {
        FocusState.IDLE -> to == FocusState.ARMED
        FocusState.ARMED -> to == FocusState.LOCKED || to == FocusState.IDLE
        FocusState.LOCKED -> to == FocusState.ENDING
        FocusState.ENDING -> to == FocusState.IDLE
    }

    fun requireTransition(from: FocusState, to: FocusState) {
        check(canTransition(from, to)) {
            "Invalid FocusForge focus transition: " + from + " -> " + to
        }
    }
}
