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

    suspend fun getDocument(documentId: String): BackendDocument =
        withContext(Dispatchers.IO) {
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
                    add(
                        BackendLibraryItem(
                            documentId = item.getString("document_id"),
                            title = item.getString("title"),
                            pinned = item.getBoolean("pinned"),
                            archived = item.getBoolean("archived"),
                            fastModeEnabled = item.getBoolean("fast_mode_enabled")
                        )
                    )
                }
            }
        }

    suspend fun updateLibrary(
        documentId: String,
        pinned: Boolean? = null,
        archived: Boolean? = null,
        fastModeEnabled: Boolean? = null
    ): BackendLibraryItem = withContext(Dispatchers.IO) {
        val params = buildList {
            pinned?.let { add("pinned=$it") }
            archived?.let { add("archived=$it") }
            fastModeEnabled?.let { add("fast_mode_enabled=$it") }
        }.joinToString("&")
        val path = "/api/v1/library/${encode(documentId)}" +
            if (params.isEmpty()) "" else "?$params"
        val item = JSONObject(request("PATCH", path))
        BackendLibraryItem(
            documentId = item.getString("document_id"),
            title = item.getString("title"),
            pinned = item.getBoolean("pinned"),
            archived = item.getBoolean("archived"),
            fastModeEnabled = item.getBoolean("fast_mode_enabled")
        )
    }

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
