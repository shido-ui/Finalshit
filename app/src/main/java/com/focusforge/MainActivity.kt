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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.focusforge.enforcement.FocusEnforcementController
import com.focusforge.data.LibraryItem
import kotlinx.coroutines.launch
import com.focusforge.focus.FocusState
import com.focusforge.launcher.AppCatalog
import com.focusforge.launcher.LaunchableApp
import com.focusforge.ui.FocusForgeViewModel
import com.focusforge.usage.UsageAccess
import com.focusforge.usage.openUsageAccessSettings

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val manager = (application as FocusForgeApplication).sessionManager
        val catalog = AppCatalog(this)
        val enforcement = FocusEnforcementController(this)
        val libraryRepository = (application as FocusForgeApplication).libraryRepository

        setContent {
            MaterialTheme {
                val viewModel: FocusForgeViewModel = viewModel(
                    factory = FocusForgeViewModel.Factory(manager)
                )
                val focusState by viewModel.focusState.collectAsState()
                var selectedMinutes by remember { mutableStateOf(25) }
                var usageGranted by remember { mutableStateOf(UsageAccess.isGranted(this@MainActivity)) }
                var enforcementError by remember { mutableStateOf<String?>(null) }
                val apps = remember { catalog.installedLaunchableApps() }
                var allowedPackages by remember {
                    mutableStateOf(setOf(packageName))
                }
                val enforcementStatus = remember { enforcement.status() }
                val libraryItems by libraryRepository.observeActive().collectAsState(initial = emptyList())
                val scope = rememberCoroutineScope()

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
                                        onClick = {
                                            enforcementError = null
                                            val enforcementStarted =
                                                !enforcementStatus.deviceOwner ||
                                                    enforcement.startLockTask(
                                                        this@MainActivity,
                                                        allowedPackages
                                                    )
                                            if (enforcementStarted) {
                                                viewModel.startFocus(selectedMinutes)
                                            } else {
                                                enforcementError =
                                                    "Focus could not start because device-owner enforcement could not be enabled."
                                            }
                                        },
                                        Modifier.fillMaxWidth()
                                    ) { Text("Start focus") }
                                } else {
                                    Button(
                                        onClick = {
                                            enforcement.stopLockTask(this@MainActivity)
                                            viewModel.cancelFocus()
                                        },
                                        Modifier.fillMaxWidth()
                                    ) { Text("End focus") }
                                }
                                enforcementError?.let {
                                    Text(
                                        it,
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                }
                                Text(
                                    if (enforcementStatus.deviceOwner) {
                                        "Dedicated-device enforcement available."
                                    } else {
                                        "Standard mode records the session; app blocking requires supported device-owner provisioning."
                                    },
                                    style = MaterialTheme.typography.bodySmall
                                )
                            }
                        }

                        Card(Modifier.fillMaxWidth()) {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text("Allowed apps", style = MaterialTheme.typography.titleMedium)
                                Text(
                                    "Select apps that may remain available during a device-owner lock-task session.",
                                    style = MaterialTheme.typography.bodySmall
                                )
                                LazyColumn(
                                    modifier = Modifier.fillMaxWidth().height(220.dp),
                                    verticalArrangement = Arrangement.spacedBy(2.dp)
                                ) {
                                    items(apps, key = { it.packageName }) { app ->
                                        AppRow(
                                            app = app,
                                            checked = allowedPackages.contains(app.packageName),
                                            onCheckedChange = { checked ->
                                                allowedPackages = if (checked) {
                                                    allowedPackages + app.packageName
                                                } else {
                                                    allowedPackages - app.packageName
                                                }
                                            }
                                        )
                                    }
                                }
                            }
                        }


                        Card(Modifier.fillMaxWidth()) {
                            Column(
                                Modifier.padding(16.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Text("Library", style = MaterialTheme.typography.titleMedium)
                                Text(
                                    "Local study material stays available on-device.",
                                    style = MaterialTheme.typography.bodySmall
                                )
                                if (libraryItems.isEmpty()) {
                                    Text(
                                        "No documents in the local library yet.",
                                        style = MaterialTheme.typography.bodyMedium
                                    )
                                } else {
                                    libraryItems.take(8).forEach { item ->
                                        LibraryRow(
                                            item = item,
                                            onPinned = {
                                                scope.launch {
                                                    libraryRepository.setPinned(item.documentId, !item.pinned)
                                                }
                                            },
                                            onFastMode = {
                                                scope.launch {
                                                    libraryRepository.setFastMode(
                                                        item.documentId,
                                                        !item.fastModeEnabled
                                                    )
                                                }
                                            },
                                            onArchive = {
                                                scope.launch {
                                                    libraryRepository.setArchived(item.documentId, true)
                                                }
                                            }
                                        )
                                    }
                                }
                            }
                        }

                        Card(Modifier.fillMaxWidth()) {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text("Usage access", style = MaterialTheme.typography.titleMedium)
                                Text(
                                    if (usageGranted) {
                                        "Granted — FocusForge can read app usage for analytics."
                                    } else {
                                        "Not granted — app-usage analytics are unavailable."
                                    }
                                )
                                if (!usageGranted) {
                                    OutlinedButton(onClick = { openUsageAccessSettings() }) {
                                        Text("Open usage access settings")
                                    }
                                } else {
                                    OutlinedButton(onClick = {
                                        usageGranted = UsageAccess.isGranted(this@MainActivity)
                                    }) {
                                        Text("Refresh permission")
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@androidx.compose.runtime.Composable
private fun AppRow(
    app: LaunchableApp,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(app.label, modifier = Modifier.padding(top = 12.dp, bottom = 12.dp))
        Checkbox(checked = checked, onCheckedChange = onCheckedChange)
    }
}


@androidx.compose.runtime.Composable
private fun LibraryRow(
    item: LibraryItem,
    onPinned: () -> Unit,
    onFastMode: () -> Unit,
    onArchive: () -> Unit
) {
    Card(Modifier.fillMaxWidth()) {
        Column(
            Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Text(item.title, style = MaterialTheme.typography.bodyLarge)
            Text(
                if (item.fastModeEnabled) "Fast Mode enabled" else "Fast Mode disabled",
                style = MaterialTheme.typography.bodySmall
            )
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                OutlinedButton(onClick = onPinned) {
                    Text(if (item.pinned) "Unpin" else "Pin")
                }
                OutlinedButton(onClick = onFastMode) {
                    Text(if (item.fastModeEnabled) "Disable Fast" else "Enable Fast")
                }
                OutlinedButton(onClick = onArchive) {
                    Text("Archive")
                }
            }
        }
    }
}

