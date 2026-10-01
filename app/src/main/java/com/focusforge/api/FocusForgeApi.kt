package com.focusforge.api

import android.content.Context
import android.net.Uri
import com.focusforge.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

class FocusForgeApi(
    private val context: Context,
    private val baseUrl: String = BuildConfig.BACKEND_BASE_URL,
    private val timeoutMs: Int = 20_000
) {
    suspend fun health(): BackendHealth = withContext(Dispatchers.IO) {
        val json = JSONObject(request("GET", "/health"))
        BackendHealth(json.getString("status"), json.getString("service"))
    }

    suspend fun ingestPdf(uri: Uri, filename: String): BackendDocument =
        withContext(Dispatchers.IO) {
            val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
                ?: throw IOException("Unable to read selected PDF")
            if (bytes.isEmpty()) throw IOException("Selected PDF is empty")
            val encoded = URLEncoder.encode(filename, Charsets.UTF_8.name())
            val json = JSONObject(request(
                method = "POST",
                path = "/api/v1/knowledge/documents?filename=$encoded",
                body = bytes,
                contentType = "application/pdf"
            ))
            parseDocument(json)
        }

    suspend fun getQuestionAssets(questionId: String): List<QuestionAsset> = withContext(Dispatchers.IO) {
        val array = JSONArray(
            request("GET", "/api/v1/knowledge/questions/${encode(questionId)}/assets")
        )
        buildList(array.length()) {
            for (index in 0 until array.length()) {
                val item = array.getJSONObject(index)
                add(
                    QuestionAsset(
                        id = item.getString("id"),
                        mimeType = item.getString("mime_type")
                    )
                )
            }
        }
    }

    suspend fun getAssetBytes(assetId: String): ByteArray = withContext(Dispatchers.IO) {
        val connection = (URL(baseUrl.trimEnd('/') + "/api/v1/knowledge/assets/${encode(assetId)}").openConnection() as HttpURLConnection)
        connection.requestMethod = "GET"
        connection.connectTimeout = timeoutMs
        connection.readTimeout = timeoutMs
        val status = connection.responseCode
        val bytes = if (status in 200..299) connection.inputStream.use { it.readBytes() } else {
            val detail = connection.errorStream?.bufferedReader()?.use { it.readText() }.orEmpty()
            throw IOException("Asset request failed ($status): $detail")
        }
        connection.disconnect()
        bytes
    }

    suspend fun getDocument(documentId: String): BackendDocument = withContext(Dispatchers.IO) {
        parseDocument(
            JSONObject(request("GET", "/api/v1/knowledge/documents/${encode(documentId)}"))
        )
    }

    suspend fun getLibrary(includeArchived: Boolean = false): List<BackendLibraryItem> =
        withContext(Dispatchers.IO) {
            val array = JSONArray(request("GET", "/api/v1/library?include_archived=$includeArchived"))
            buildList(array.length()) {
                for (index in 0 until array.length()) {
                    val item = array.getJSONObject(index)
                    add(parseLibraryItem(item))
                }
            }
        }

    suspend fun updateLibrary(
        documentId: String,
        pinned: Boolean? = null,
        archived: Boolean? = null,
        fastModeEnabled: Boolean? = null
    ): BackendLibraryItem = withContext(Dispatchers.IO) {
        val body = JSONObject().apply {
            pinned?.let { put("pinned", it) }
            archived?.let { put("archived", it) }
            fastModeEnabled?.let { put("fast_mode_enabled", it) }
        }.toString().toByteArray(Charsets.UTF_8)
        parseLibraryItem(
            JSONObject(
                request(
                    "PATCH",
                    "/api/v1/library/${encode(documentId)}",
                    body = body,
                    contentType = "application/json"
                )
            )
        )
    }

    suspend fun startPractice(
        mode: String = "fast",
        limit: Int = 10,
        documentId: String? = null,
        taxonomyNodeId: String? = null
    ): PracticeStart = withContext(Dispatchers.IO) {
        require(limit in 1..100) { "Practice limit must be between 1 and 100" }
        val body = JSONObject().apply {
            put("mode", mode)
            put("limit", limit)
            documentId?.let { put("document_id", it) }
            taxonomyNodeId?.let { put("taxonomy_node_id", it) }
        }.toString().toByteArray(Charsets.UTF_8)
        val json = JSONObject(
            request(
                method = "POST",
                path = "/api/v1/practice/sessions",
                body = body,
                contentType = "application/json"
            )
        )
        val sessionJson = json.getJSONObject("session")
        val questionsJson = json.getJSONArray("questions")
        PracticeStart(
            session = parsePracticeSession(sessionJson),
            questions = buildList(questionsJson.length()) {
                for (index in 0 until questionsJson.length()) {
                    add(parsePracticeQuestion(questionsJson.getJSONObject(index)))
                }
            }
        )
    }

    suspend fun submitPractice(
        sessionId: String,
        answers: Map<String, String>
    ): PracticeResult = withContext(Dispatchers.IO) {
        val answersJson = JSONObject().apply {
            answers.forEach { (id, answer) -> put(id, answer) }
        }
        val body = JSONObject().apply { put("answers", answersJson) }
            .toString().toByteArray(Charsets.UTF_8)
        val json = JSONObject(
            request(
                method = "POST",
                path = "/api/v1/practice/sessions/${encode(sessionId)}/submit",
                body = body,
                contentType = "application/json"
            )
        )
        val resultJson = json.getJSONObject("question_results")
        val results = buildMap(resultJson.length()) {
            val keys = resultJson.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                put(key, resultJson.getBoolean(key))
            }
        }
        PracticeResult(
            sessionId = json.getString("session_id"),
            score = json.getInt("score"),
            total = json.getInt("total"),
            answered = json.getInt("answered"),
            correct = json.getInt("correct"),
            percentage = json.getDouble("percentage"),
            questionResults = results
        )
    }

    suspend fun getWeaknesses(limit: Int = 20): List<WeaknessProfile> = withContext(Dispatchers.IO) {
        require(limit in 1..500) { "Weakness limit must be between 1 and 500" }
        val array = JSONArray(request("GET", "/api/v1/intelligence/weaknesses?limit=$limit"))
        buildList(array.length()) {
            for (index in 0 until array.length()) {
                add(parseWeakness(array.getJSONObject(index)))
            }
        }
    }

    suspend fun getDueReviewQuestionIds(limit: Int = 100): List<String> = withContext(Dispatchers.IO) {
        require(limit in 1..500) { "Review limit must be between 1 and 500" }
        val array = JSONArray(request("GET", "/api/v1/intelligence/reviews/due?limit=$limit"))
        buildList(array.length()) {
            for (index in 0 until array.length()) add(array.getString(index))
        }
    }

    suspend fun getReviewState(questionId: String): ReviewState = withContext(Dispatchers.IO) {
        parseReviewState(
            JSONObject(request("GET", "/api/v1/intelligence/reviews/${encode(questionId)}"))
        )
    }

    private fun parseWeakness(json: JSONObject) = WeaknessProfile(
        taxonomyNodeId = json.getString("taxonomy_node_id"),
        attempts = json.getInt("attempts"),
        correct = json.getInt("correct"),
        incorrect = json.getInt("incorrect"),
        accuracy = json.getDouble("accuracy"),
        mastery = json.getDouble("mastery"),
        lastAttemptAt = json.optString("last_attempt_at").takeIf { it.isNotBlank() && it != "null" }
    )

    private fun parseReviewState(json: JSONObject) = ReviewState(
        questionId = json.getString("question_id"),
        repetitions = json.getInt("repetitions"),
        intervalDays = json.getInt("interval_days"),
        easeFactor = json.getDouble("ease_factor"),
        dueAt = json.getString("due_at"),
        lastReviewedAt = json.optString("last_reviewed_at").takeIf { it.isNotBlank() && it != "null" },
        lastCorrect = if (json.isNull("last_correct")) null else json.getBoolean("last_correct")
    )

    private fun parseLibraryItem(item: JSONObject) = BackendLibraryItem(
        documentId = item.getString("document_id"),
        title = item.getString("title"),
        pinned = item.getBoolean("pinned"),
        archived = item.getBoolean("archived"),
        fastModeEnabled = item.getBoolean("fast_mode_enabled")
    )

    private fun parsePracticeSession(json: JSONObject) = PracticeSession(
        id = json.getString("id"),
        mode = json.getString("mode"),
        questionIds = json.getJSONArray("question_ids").let { array ->
            buildList(array.length()) { for (i in 0 until array.length()) add(array.getString(i)) }
        },
        startedAt = json.getString("started_at"),
        submittedAt = json.optString("submitted_at").takeIf { it.isNotBlank() && it != "null" },
        score = if (json.isNull("score")) null else json.getInt("score"),
        total = json.getInt("total"),
        answered = json.getInt("answered")
    )

    private fun parsePracticeQuestion(json: JSONObject) = PracticeQuestion(
        id = json.getString("id"),
        position = json.getInt("position"),
        text = json.getString("text"),
        options = json.optJSONObject("options")?.let { options ->
            buildMap(options.length()) {
                val keys = options.keys()
                while (keys.hasNext()) {
                    val key = keys.next()
                    put(key, options.getString(key))
                }
            }
        } ?: emptyMap(),
        taxonomyNodeId = json.optString("taxonomy_node_id").takeIf { it.isNotBlank() && it != "null" },
        difficulty = json.optString("difficulty").takeIf { it.isNotBlank() && it != "null" },
        hasDiagram = json.optBoolean("has_diagram", false),
        hasTable = json.optBoolean("has_table", false),
        assetIds = json.optJSONArray("asset_ids")?.let { array ->
            buildList(array.length()) { for (i in 0 until array.length()) add(array.getString(i)) }
        } ?: emptyList()
    )

    private fun request(
        method: String,
        path: String,
        body: ByteArray? = null,
        contentType: String? = null
    ): String {
        val connection = (URL(baseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection)
        connection.requestMethod = method
        connection.connectTimeout = timeoutMs
        connection.readTimeout = timeoutMs
        connection.setRequestProperty("Accept", "application/json")
        if (body != null) {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", contentType ?: "application/octet-stream")
            connection.setFixedLengthStreamingMode(body.size)
            connection.outputStream.use { it.write(body) }
        }

        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val response = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
        connection.disconnect()

        if (status !in 200..299) {
            val detail = runCatching { JSONObject(response).optString("detail") }.getOrNull()
            throw IOException(
                "Backend request failed ($status)" +
                    if (!detail.isNullOrBlank()) ": $detail" else ""
            )
        }
        return response
    }

    private fun parseDocument(json: JSONObject): BackendDocument =
        BackendDocument(
            id = json.getString("id"),
            filename = json.getString("filename"),
            pageCount = json.getInt("page_count"),
            status = json.getString("status"),
            error = json.optString("error").takeIf { it.isNotBlank() && it != "null" },
            questionCount = json.optInt("question_count", 0)
        )

    private fun encode(value: String): String = URLEncoder.encode(value, Charsets.UTF_8.name())
}

data class QuestionAsset(
    val id: String,
    val mimeType: String
)
