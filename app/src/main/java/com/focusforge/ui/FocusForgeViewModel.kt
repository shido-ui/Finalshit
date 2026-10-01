package com.focusforge.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.focusforge.focus.FocusSessionManager
import com.focusforge.focus.FocusState
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class FocusForgeViewModel(
    private val manager: FocusSessionManager
) : ViewModel() {
    val focusState: StateFlow<FocusState> = manager.state

    init {
        viewModelScope.launch { manager.recover() }
    }

    suspend fun startFocus(minutes: Int): Boolean {
        require(minutes > 0)
        return manager.start(minutes * 60_000L)
    }

    fun cancelFocus() {
        manager.cancel()
    }

    class Factory(
        private val manager: FocusSessionManager
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            require(modelClass.isAssignableFrom(FocusForgeViewModel::class.java))
            return FocusForgeViewModel(manager) as T
        }
    }
}
