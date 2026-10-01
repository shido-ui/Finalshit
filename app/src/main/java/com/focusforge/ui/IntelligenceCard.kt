package com.focusforge.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.focusforge.api.BackendRepository
import com.focusforge.api.WeaknessProfile
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

@Composable
fun IntelligenceCard(
    repository: BackendRepository,
    onStartAdaptive: () -> Unit,
    modifier: Modifier = Modifier
) {
    val scope = rememberCoroutineScope()
    var weaknesses by remember { mutableStateOf<List<WeaknessProfile>>(emptyList()) }
    var dueCount by remember { mutableStateOf(0) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    fun refresh() {
        loading = true
        error = null
        scope.launch {
            runCatching {
                val profiles = repository.getWeaknesses(20)
                val due = repository.getDueReviewQuestionIds(100)
                profiles to due.size
            }.onSuccess { (profiles, due) ->
                weaknesses = profiles
                dueCount = due
            }.onFailure {
                error = it.message ?: "Unable to load learning intelligence"
            }
            loading = false
        }
    }

    Card(modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Adaptive Learning", style = MaterialTheme.typography.titleMedium)
            Text("Revision priority is based on observed mistakes, mastery and due reviews.", style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(enabled = !loading, onClick = onStartAdaptive) { Text("Use Adaptive Practice") }
                OutlinedButton(enabled = !loading, onClick = { refresh() }) {
                    Text(if (loading) "Refreshing…" else "Refresh")
                }
            }
            Text("Reviews due: $" + "{dueCount}", style = MaterialTheme.typography.bodyLarge)
            if (weaknesses.isEmpty() && !loading) {
                Text("No weakness profile yet. Complete practice questions to build your revision profile.", style = MaterialTheme.typography.bodySmall)
            } else {
                LazyColumn(modifier = Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(weaknesses, key = { it.taxonomyNodeId }) { profile ->
                        Card(Modifier.fillMaxWidth()) {
                            Column(Modifier.padding(10.dp)) {
                                Text(profile.taxonomyNodeId, style = MaterialTheme.typography.bodyLarge)
                                Text("Mastery $" + "{percent(profile.mastery)}% • Accuracy $" + "{percent(profile.accuracy)}% • $" + "{profile.attempts} attempts", style = MaterialTheme.typography.bodySmall)
                                Text("$" + "{profile.incorrect} incorrect • $" + "{profile.correct} correct", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
            }
            error?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        }
    }
}

private fun percent(value: Double): Int = (value * 100.0).roundToInt().coerceIn(0, 100)
