package com.focusforge

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.focusforge.focus.FocusState
import com.focusforge.ui.FocusForgeViewModel
import com.focusforge.usage.UsageAccess
import com.focusforge.usage.openUsageAccessSettings

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val manager = (application as FocusForgeApplication).sessionManager

        setContent {
            MaterialTheme {
                val viewModel: FocusForgeViewModel = viewModel(
                    factory = FocusForgeViewModel.Factory(manager)
                )
                val focusState by viewModel.focusState.collectAsState()
                var selectedMinutes by remember { mutableStateOf(25) }
                val usageGranted = remember { mutableStateOf(UsageAccess.isGranted(this@MainActivity)) }

                Surface(Modifier.fillMaxSize()) {
                    Column(
                        Modifier.fillMaxSize().padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        Text("FocusForge", style = MaterialTheme.typography.headlineLarge)
                        Text(
                            when (focusState) {
                                FocusState.IDLE -> "Ready for a focused study session."
                                FocusState.ARMED -> "Preparing your focus session."
                                FocusState.LOCKED -> "Focus session active."
                                FocusState.ENDING -> "Finishing your focus session."
                            }
                        )

                        Card(Modifier.fillMaxWidth()) {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text("Session", style = MaterialTheme.typography.titleMedium)
                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    listOf(25, 50, 90).forEach { minutes ->
                                        OutlinedButton(onClick = { selectedMinutes = minutes }) {
                                            Text(minutes.toString() + "m")
                                        }
                                    }
                                }
                                Spacer(Modifier.height(2.dp))
                                if (focusState == FocusState.IDLE) {
                                    Button(
                                        onClick = { viewModel.startFocus(selectedMinutes) },
                                        Modifier.fillMaxWidth()
                                    ) { Text("Start focus") }
                                } else {
                                    Button(
                                        onClick = viewModel::cancelFocus,
                                        Modifier.fillMaxWidth()
                                    ) { Text("End focus") }
                                }
                            }
                        }

                        Card(Modifier.fillMaxWidth()) {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text("Usage access", style = MaterialTheme.typography.titleMedium)
                                Text(
                                    if (usageGranted.value) {
                                        "Granted — FocusForge can read app usage for analytics."
                                    } else {
                                        "Not granted — app-usage analytics are unavailable."
                                    }
                                )
                                if (!usageGranted.value) {
                                    OutlinedButton(onClick = {
                                        openUsageAccessSettings()
                                    }) { Text("Open usage access settings") }
                                } else {
                                    OutlinedButton(onClick = {
                                        usageGranted.value = UsageAccess.isGranted(this@MainActivity)
                                    }) { Text("Refresh permission") }
                                }
                            }
                        }

                        Text(
                            "FocusForge currently records sessions and usage. It does not pretend to block apps without an Android mechanism that can actually enforce it.",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }
        }
    }
}
