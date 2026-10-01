package com.focusforge.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.focusforge.api.BackendRepository
import com.focusforge.api.CopilotAnswer
import com.focusforge.data.LibraryItem
import kotlinx.coroutines.launch

@Composable
fun CopilotCard(
    repository: BackendRepository,
    libraryItems: List<LibraryItem>,
    modifier: Modifier = Modifier
) {
    val scope = rememberCoroutineScope()
    var selectedDocumentId by remember { mutableStateOf<String?>(null) }
    var question by remember { mutableStateOf("") }
    var pageStart by remember { mutableIntStateOf(1) }
    var pageEnd by remember { mutableIntStateOf(1) }
    var answer by remember { mutableStateOf<CopilotAnswer?>(null) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    Card(modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Study Copilot", style = MaterialTheme.typography.titleMedium)
            Text("Ask questions against selected PDF pages. Answers are returned with source citations.", style = MaterialTheme.typography.bodySmall)
            if (libraryItems.isEmpty()) {
                Text("Import a PDF first to use Study Copilot.")
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    libraryItems.take(4).forEach { item ->
                        Button(
                            enabled = !busy,
                            onClick = { selectedDocumentId = item.documentId }
                        ) {
                            Text(if (selectedDocumentId == item.documentId) "✓ " + item.title.take(12) else item.title.take(12))
                        }
                    }
                }
                OutlinedTextField(
                    value = question,
                    onValueChange = { question = it },
                    label = { Text("Ask about your material") },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !busy
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = pageStart.toString(),
                        onValueChange = { it.toIntOrNull()?.takeIf { value -> value >= 1 }?.let { value -> pageStart = value } },
                        label = { Text("From page") },
                        modifier = Modifier.weight(1f),
                        enabled = !busy
                    )
                    OutlinedTextField(
                        value = pageEnd.toString(),
                        onValueChange = { it.toIntOrNull()?.takeIf { value -> value >= pageStart }?.let { value -> pageEnd = value } },
                        label = { Text("To page") },
                        modifier = Modifier.weight(1f),
                        enabled = !busy
                    )
                }
                Button(
                    enabled = !busy && selectedDocumentId != null && question.isNotBlank(),
                    onClick = {
                        val documentId = selectedDocumentId ?: return@Button
                        busy = true
                        error = null
                        answer = null
                        scope.launch {
                            runCatching { repository.askCopilot(documentId, question, pageStart, pageEnd) }
                                .onSuccess { answer = it }
                                .onFailure { error = it.message ?: "Study Copilot failed" }
                            busy = false
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(if (busy) "Thinking…" else "Ask Copilot")
                }
                answer?.let { result ->
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(result.answer, style = MaterialTheme.typography.bodyLarge)
                            Text("Sources: pages " + result.citations.joinToString(", "), style = MaterialTheme.typography.bodySmall)
                            Text("Confidence: " + (result.confidence * 100).toInt() + "%", style = MaterialTheme.typography.bodySmall)
                            Text(result.evidence, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                error?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            }
        }
    }
}
