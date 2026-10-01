package com.focusforge

import android.content.Context
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.focusforge.api.BackendDocument
import com.focusforge.api.BackendHealth
import com.focusforge.api.BackendRepository
import com.focusforge.data.LibraryItem
import com.focusforge.enforcement.FocusEnforcementController
import com.focusforge.focus.FocusState
import com.focusforge.launcher.AppCatalog
import com.focusforge.launcher.LaunchableApp
import com.focusforge.ui.FocusForgeViewModel
import com.focusforge.ui.IntelligenceCard
import com.focusforge.ui.PracticeCard
import com.focusforge.usage.UsageAccess
import com.focusforge.usage.openUsageAccessSettings
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = application as FocusForgeApplication
        val manager = app.sessionManager
        val catalog = AppCatalog(this)
        val enforcement = FocusEnforcementController(this)
        val libraryRepository = app.libraryRepository
        val backendRepository = app.backendRepository

        setContent {
            MaterialTheme {
                val viewModel: FocusForgeViewModel = viewModel(
                    factory = FocusForgeViewModel.Factory(manager)
                )
                val focusState by viewModel.focusState.collectAsState()
                var selectedMinutes by remember { mutableStateOf(25) }
                var usageGranted by remember { mutableStateOf(UsageAccess.isGranted(this@MainActivity)) }
                var enforcementError by remember { mutableStateOf<String?>(null) }
                var backendHealth by remember { mutableStateOf<BackendHealth?>(null) }
                var backendError by remember { mutableStateOf<String?>(null) }
                var importBusy by remember { mutableStateOf(false) }
                var importError by remember { mutableStateOf<String?>(null) }
                var lastImported by remember { mutableStateOf<BackendDocument?>(null) }
                var adaptiveLaunchToken by remember { mutableStateOf(0) }
                val apps = remember { catalog.installedLaunchableApps() }
                var allowedPackages by remember { mutableStateOf(setOf(packageName)) }
                val enforcementStatus = remember { enforcement.status() }
                val libraryItems by libraryRepository.observeActive().collectAsState(initial = emptyList())
                val scope = rememberCoroutineScope()
                val picker = rememberLauncherForActivityResult(
                    ActivityResultContracts.OpenDocument()
                ) { uri ->
                    if (uri == null) return@rememberLauncherForActivityResult
                    scope.launch {
                        importBusy = true
                        importError = null
                        runCatching {
                            val document = backendRepository.importPdf(uri, displayName(uri))
                            lastImported = document
                            libraryRepository.upsert(
                                LibraryItem(
                                    id = "library-${document.id}",
                                    documentId = document.id,
                                    title = document.filename,
                                    createdAt = System.currentTimeMillis(),
                                    updatedAt = System.currentTimeMillis()
                                )
                            )
                        }.onFailure {
                            importError = it.message ?: "PDF import failed"
                        }
                        importBusy = false
                    }
                }

                LaunchedEffect(Unit) {
                    runCatching {
                        backendHealth = backendRepository.checkHealth()
                        backendRepository.syncLibrary().forEach { item ->
                            libraryRepository.upsert(
                                LibraryItem(
                                    id = "library-${item.documentId}",
                                    documentId = item.documentId,
                                    title = item.title,
                                    pinned = item.pinned,
                                    archived = item.archived,
                                    fastModeEnabled = item.fastModeEnabled,
                                    createdAt = System.currentTimeMillis(),
                                    updatedAt = System.currentTimeMillis()
                                )
                            )
                        }
                    }.onFailure {
                        backendError = it.message ?: "Backend unavailable"
                    }
                }

                Surface(Modifier.fillMaxSize()) {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize().padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        item {
                            Text("FocusForge", style = MaterialTheme.typography.headlineLarge)
                        }
                        item {
                            Text(
                                when (focusState) {
                                    FocusState.IDLE -> "Ready for a focused study session."
                                    FocusState.ARMED -> "Preparing your focus session."
                                    FocusState.LOCKED -> "Focus session active."
                                    FocusState.ENDING -> "Finishing your focus session."
                                }
                            )
                        }
                        item {
                            Card(Modifier.fillMaxWidth()) {
                                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text("Backend", style = MaterialTheme.typography.titleMedium)
                                    Text(
                                        when {
                                            backendHealth != null -> "Connected: " + backendHealth!!.service
                                            backendError != null -> "Offline: " + backendError
                                            else -> "Checking backend…"
                                        },
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                    OutlinedButton(
                                        enabled = !importBusy,
                                        onClick = { picker.launch(arrayOf("application/pdf")) }
                                    ) {
                                        Text(if (importBusy) "Importing PDF…" else "Import PDF")
                                    }
                                    lastImported?.let { document ->
                                        Text(
                                            document.filename + " • " + document.status +
                                                " • " + document.questionCount + " questions",
                                            style = MaterialTheme.typography.bodySmall
                                        )
                                    }
                                    importError?.let {
                                        Text(it, style = MaterialTheme.typography.bodySmall)
                                    }
                                }
                            }
                        }
                        item {
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
                                                scope.launch {
                                                    val sessionStarted = viewModel.startFocus(selectedMinutes)
                                                    if (!sessionStarted) {
                                                        enforcementError = "A focus session is already active."
                                                        return@launch
                                                    }
                                                    val status = enforcement.status()
                                                    if (status.deviceOwner &&
                                                        !enforcement.startLockTask(
                                                            this@MainActivity,
                                                            allowedPackages
                                                        )
                                                    ) {
                                                        viewModel.cancelFocus()
                                                        enforcementError =
                                                            "Focus could not start because device-owner enforcement could not be enabled."
                                                    }
                                                }
                                            },
                                            modifier = Modifier.fillMaxWidth()
                                        ) {
                                            Text("Start focus")
                                        }
                                    } else {
                                        Button(
                                            onClick = {
                                                enforcement.stopLockTask(this@MainActivity)
                                                viewModel.cancelFocus()
                                            },
                                            modifier = Modifier.fillMaxWidth()
                                        ) {
                                            Text("End focus")
                                        }
                                    }
                                    enforcementError?.let {
                                        Text(it, style = MaterialTheme.typography.bodySmall)
                                    }
                                    Text(
                                        if (enforcement.status().deviceOwner) {
                                            "Dedicated-device enforcement available."
                                        } else {
                                            "Standard mode records the session; app blocking requires supported device-owner provisioning."
                                        },
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                }
                            }
                        }
                        item {
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
                        }
                        item {
                            Card(Modifier.fillMaxWidth()) {
                                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text("Library", style = MaterialTheme.typography.titleMedium)
                                    Text(
                                        "Local study material stays available on-device.",
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                    if (libraryItems.isEmpty()) {
                                        Text("No documents in the local library yet.")
                                    } else {
                                        libraryItems.take(8).forEach { libraryItem ->
                                            LibraryRow(
                                                item = libraryItem,
                                                onPinned = {
                                                    scope.launch {
                                                        val value = !libraryItem.pinned
                                                        runCatching {
                                                            backendRepository.updateLibrary(
                                                                libraryItem.documentId,
                                                                pinned = value
                                                            )
                                                        }
                                                        libraryRepository.setPinned(
                                                            libraryItem.documentId,
                                                            value
                                                        )
                                                    }
                                                },
                                                onFastMode = {
                                                    scope.launch {
                                                        val value = !libraryItem.fastModeEnabled
                                                        runCatching {
                                                            backendRepository.updateLibrary(
                                                                libraryItem.documentId,
                                                                fastModeEnabled = value
                                                            )
                                                        }
                                                        libraryRepository.setFastMode(
                                                            libraryItem.documentId,
                                                            value
                                                        )
                                                    }
                                                },
                                                onArchive = {
                                                    scope.launch {
                                                        runCatching {
                                                            backendRepository.updateLibrary(
                                                                libraryItem.documentId,
                                                                archived = true
                                                            )
                                                        }
                                                        libraryRepository.setArchived(
                                                            libraryItem.documentId,
                                                            true
                                                        )
                                                    }
                                                }
                                            )
                                        }
                                    }
                                }
                            }
                        }
                        item {
                            IntelligenceCard(
                                repository = backendRepository,
                                onStartAdaptive = { adaptiveLaunchToken += 1 }
                            )
                        }
                        item {
                            PracticeCard(
                                repository = backendRepository,
                                libraryItems = libraryItems,
                                adaptiveLaunchToken = adaptiveLaunchToken
                            )
                        }
                        item {
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
                                        OutlinedButton(
                                            onClick = {
                                                usageGranted = UsageAccess.isGranted(this@MainActivity)
                                            }
                                        ) {
                                            Text("Refresh permission")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

    private fun displayName(uri: Uri): String {
        val fallback = uri.lastPathSegment?.substringAfterLast('/')?.takeIf { it.isNotBlank() }
            ?: "document.pdf"
        val projection = arrayOf(OpenableColumns.DISPLAY_NAME)
        return runCatching {
            contentResolver.query(uri, projection, null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) {
                    cursor.getString(0)?.takeIf { it.isNotBlank() }
                } else null
            } ?: fallback
        }.getOrDefault(fallback)
    }
}

@Composable
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

@Composable
private fun LibraryRow(
    item: LibraryItem,
    onPinned: () -> Unit,
    onFastMode: () -> Unit,
    onArchive: () -> Unit
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
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
