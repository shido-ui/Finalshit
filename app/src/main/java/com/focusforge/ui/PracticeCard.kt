package com.focusforge.ui

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.focusforge.data.LibraryItem
import com.focusforge.api.BackendRepository
import com.focusforge.api.PracticeQuestion
import com.focusforge.api.PracticeResult
import kotlinx.coroutines.launch

@Composable
fun PracticeCard(
    repository: BackendRepository,
    libraryItems: List<LibraryItem>,
    adaptiveLaunchToken: Int = 0,
    modifier: Modifier = Modifier
) {
    val scope = rememberCoroutineScope()
    var selectedDocumentId by remember { mutableStateOf<String?>(null) }
    var mode by remember { mutableStateOf("fast") }
    var limit by remember { mutableIntStateOf(10) }
    var questions by remember { mutableStateOf<List<PracticeQuestion>>(emptyList()) }
    var sessionId by remember { mutableStateOf<String?>(null) }
    var result by remember { mutableStateOf<PracticeResult?>(null) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var completedQuestions by remember { mutableStateOf<List<PracticeQuestion>>(emptyList()) }
    val answers = remember { mutableStateMapOf<String, String>() }

    LaunchedEffect(adaptiveLaunchToken) {
        if (adaptiveLaunchToken > 0 && sessionId == null) {
            mode = "adaptive"
            result = null
            error = null
        }
    }

    Card(modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Question Bank", style = MaterialTheme.typography.titleMedium)
            Text("Practice extracted questions directly from the backend.", style = MaterialTheme.typography.bodySmall)

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("fast" to "Fast", "test" to "Test", "adaptive" to "Adaptive").forEach { (value, label) ->
                    OutlinedButton(enabled = !busy && sessionId == null, onClick = { mode = value }) {
                        Text(if (mode == value) "✓ $label" else label)
                    }
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(10, 20, 50).forEach { count ->
                    OutlinedButton(enabled = !busy && sessionId == null, onClick = { limit = count }) {
                        Text(if (limit == count) "✓ $count" else "$count")
                    }
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(enabled = !busy && sessionId == null, onClick = { selectedDocumentId = null }) {
                    Text(if (selectedDocumentId == null) "✓ All" else "All")
                }
                libraryItems.take(4).forEach { item ->
                    OutlinedButton(
                        enabled = !busy && sessionId == null,
                        onClick = { selectedDocumentId = item.documentId }
                    ) {
                        Text(if (selectedDocumentId == item.documentId) "✓ ${item.title.take(16)}" else item.title.take(16))
                    }
                }
            }

            if (sessionId == null) {
                Button(
                    enabled = !busy && libraryItems.isNotEmpty(),
                    onClick = {
                        busy = true
                        error = null
                        result = null
                        answers.clear()
                        scope.launch {
                            runCatching {
                                repository.startPractice(
                                    mode = mode,
                                    limit = limit,
                                    documentId = selectedDocumentId
                                )
                            }.onSuccess { started ->
                                sessionId = started.session.id
                                questions = started.questions
                            }.onFailure {
                                error = it.message ?: "Unable to start practice"
                            }
                            busy = false
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(if (busy) "Loading questions…" else "Start practice")
                }
            } else {
                Text("${questions.size} questions • ${mode.replaceFirstChar { it.uppercase() }} mode", style = MaterialTheme.typography.bodySmall)
                LazyColumn(
                    modifier = Modifier.fillMaxWidth().height(520.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(questions, key = { it.id }) { question ->
                        QuestionCard(
                            question = question,
                            selectedAnswer = answers[question.id].orEmpty(),
                            onAnswer = { answers[question.id] = it },
                            repository = repository
                        )
                    }
                }
                Button(
                    enabled = !busy,
                    onClick = {
                        busy = true
                        error = null
                        scope.launch {
                            runCatching {
                                repository.submitPractice(sessionId!!, answers.toMap())
                            }.onSuccess {
                                result = it
                                completedQuestions = questions
                                sessionId = null
                                questions = emptyList()
                            }.onFailure {
                                error = it.message ?: "Unable to submit practice"
                            }
                            busy = false
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(if (busy) "Submitting…" else "Submit practice")
                }
            }

            result?.let { completed ->
                Text(
                    "Result: " + completed.correct + "/" + completed.total +
                        " correct • " + completed.percentage + "%",
                    style = MaterialTheme.typography.titleSmall
                )
                Text(completed.answered.toString() + " answered", style = MaterialTheme.typography.bodySmall)
                completedQuestions.forEach { question ->
                    Text(
                        "Q" + question.position + ": " + when (completed.questionResults[question.id]) {
                            true -> "Correct"
                            false -> "Incorrect"
                            null -> "Not graded"
                        },
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }

            if (questions.isEmpty() && libraryItems.isEmpty()) {
                Text("Import a PDF first to populate the Question Bank.")
            }

            error?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            Spacer(Modifier.height(2.dp))
        }
    }
}

@Composable
private fun QuestionCard(
    question: PracticeQuestion,
    selectedAnswer: String,
    onAnswer: (String) -> Unit,
    repository: BackendRepository
) {
    var solution by remember(question.id) { mutableStateOf<com.focusforge.api.QuestionSolution?>(null) }
    var assetBytes by remember(question.id) { mutableStateOf<ByteArray?>(null) }
    var detailBusy by remember(question.id) { mutableStateOf(false) }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("${question.position}. ${question.text}", style = MaterialTheme.typography.bodyLarge)
            question.difficulty?.let {
                Text("Difficulty: $it", style = MaterialTheme.typography.bodySmall)
            }
            if (question.hasDiagram || question.hasTable) {
                Text(
                    listOfNotNull(
                        if (question.hasDiagram) "Diagram" else null,
                        if (question.hasTable) "Table" else null
                    ).joinToString(" • "),
                    style = MaterialTheme.typography.bodySmall
                )
                OutlinedButton(
                    enabled = !detailBusy,
                    onClick = {
                        detailBusy = true
                        kotlinx.coroutines.MainScope().launch {
                            runCatching {
                                repository.getQuestionAssets(question.id).firstOrNull()?.let { asset ->
                                    assetBytes = repository.getAssetBytes(asset.id)
                                }
                            }
                            detailBusy = false
                        }
                    }
                ) {
                    Text(if (detailBusy) "Loading visual…" else "View visual")
                }
                assetBytes?.let { bytes ->
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.let { bitmap ->
                        Image(
                            bitmap = bitmap.asImageBitmap(),
                            contentDescription = "Question visual",
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }
            }

            OutlinedButton(
                enabled = !detailBusy,
                onClick = {
                    detailBusy = true
                    kotlinx.coroutines.MainScope().launch {
                        runCatching {
                            solution = repository.getQuestionSolution(question.id)
                        }.recoverCatching {
                            solution = repository.generateQuestionSolution(question.id)
                        }
                        detailBusy = false
                    }
                }
            ) {
                Text(if (detailBusy) "Loading solution…" else "View solution")
            }
            solution?.let { item ->
                Text("Method: " + item.method, style = MaterialTheme.typography.bodyMedium)
                item.steps.forEachIndexed { index, step ->
                    Text((index + 1).toString() + ". " + step, style = MaterialTheme.typography.bodySmall)
                }
                Text("Final answer: " + item.finalAnswer, style = MaterialTheme.typography.bodyMedium)
                Text(item.validationReason, style = MaterialTheme.typography.bodySmall)
            }

            if (question.options.isNotEmpty()) {
                question.options.toSortedMap().forEach { (label, text) ->
                    Row(Modifier.fillMaxWidth()) {
                        RadioButton(selected = selectedAnswer == label, onClick = { onAnswer(label) })
                        Text("$label. $text", modifier = Modifier.padding(top = 12.dp))
                    }
                }
            } else {
                OutlinedTextField(
                    value = selectedAnswer,
                    onValueChange = onAnswer,
                    label = { Text("Answer") },
                    modifier = Modifier.fillMaxWidth()
                )
            }
        }
    }
}
