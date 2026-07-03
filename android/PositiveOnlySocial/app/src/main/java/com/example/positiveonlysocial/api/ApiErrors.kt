package com.example.positiveonlysocial.api

import com.google.gson.Gson
import com.google.gson.JsonObject
import retrofit2.Response
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException

/**
 * Maps API failures to friendly, user-facing text.
 *
 * The backend returns a JSON `{"error": "..."}` body for handled errors, and
 * that copy is already human-readable, so it is passed through unchanged. But a
 * gateway timeout, a routing failure, or a network drop returns HTML, an empty
 * body, or throws — so instead of leaking a raw response body, a status code, or
 * a low-level exception message to the user, those are mapped to plain language.
 *
 * Parsing uses Gson rather than `org.json` so the backend message is extracted
 * the same way in production and in local unit tests (where `org.json` is a
 * stubbed Android class that returns default values).
 */
object ApiErrors {

    private val gson = Gson()

    /**
     * Maps backend raw field tokens to friendly display names.
     */
    private val tokenMap = mapOf(
        "USERNAME" to "Username",
        "EMAIL" to "Email",
        "PASSWORD" to "Password",
        "USERNAME_OR_EMAIL" to "Username or email",
        "USER_ID" to "User ID",
        "IMAGE_URL" to "Image URL",
        "COMMENT" to "Comment",
        "RESET_TOKEN" to "Reset token",
        "VERIFICATION_TOKEN" to "Verification token",
        "IP" to "IP address",
        "SESSION_MANAGEMENT_TOKEN" to "Session token",
        "SERIES_IDENTIFIER" to "Series identifier",
        "LOGIN_COOKIE_TOKEN" to "Cookie token",
        "REMEMBER_ME" to "Remember me flag",
        "CAPTION" to "Caption",
        "POST_IDENTIFIER" to "Post identifier",
        "REASON" to "Reason",
        "COMMENT_TEXT" to "Comment text",
        "COMMENT_THREAD_IDENTIFIER" to "Comment thread identifier",
        "COMMENT_IDENTIFIER" to "Comment identifier",
        "USERNAME_FRAGMENT" to "Username fragment",
        "DATE_OF_BIRTH" to "Date of birth",
        "TARGET_TYPE" to "Target type",
        "TARGET_IDENTIFIER" to "Target identifier"
    )

    /**
     * Friendly message for an unsuccessful Retrofit [response]. Prefers the
     * backend's own `error` message; otherwise maps the HTTP status code, and
     * finally falls back to [fallback] for unmapped codes.
     */
    fun messageFor(response: Response<*>, fallback: String): String {
        val backendError = try {
            val body = response.errorBody()?.string()
            if (body.isNullOrBlank()) {
                null
            } else {
                gson.fromJson(body, JsonObject::class.java)
                    ?.get("error")
                    ?.takeIf { it.isJsonPrimitive }
                    ?.asString
                    ?.ifBlank { null }
            }
        } catch (e: Exception) {
            null
        }
        val sanitizedError = backendError?.let { sanitizeErrorMessage(it) }
        return sanitizedError ?: statusMessage(response.code(), fallback)
    }

    /**
     * Friendly message for a thrown [throwable] (a transport/network failure,
     * before any HTTP response is received).
     */
    fun messageFor(throwable: Throwable, fallback: String): String = when (throwable) {
        is SocketTimeoutException ->
            "The request timed out. Please check your connection and try again."
        is UnknownHostException, is ConnectException ->
            "We couldn't reach the server. Please check your connection and try again."
        is IOException ->
            "A network error occurred. Please check your connection and try again."
        else -> fallback
    }

    private fun statusMessage(code: Int, fallback: String): String = when (code) {
        404 -> "We couldn't find what you were looking for. It may have been removed."
        408 -> "The request timed out. Please try again."
        429 -> "You're doing that too often. Please wait a moment and try again."
        502, 503, 504 -> "The server is taking too long to respond. Please try again in a moment."
        in 500..599 -> "The server ran into a problem. Please try again in a moment."
        else -> fallback
    }

    /**
     * Sanitizes backend raw token error messages into human-legible sentences.
     */
    fun sanitizeErrorMessage(message: String): String {
        val invalidFieldsPrefix = "Invalid fields"
        val invalidPrefix = "Invalid "
        
        val suffix: String
        val isInvalidFields: Boolean
        
        if (message.startsWith(invalidFieldsPrefix)) {
            suffix = message.substring(invalidFieldsPrefix.length)
            isInvalidFields = true
        } else if (message.startsWith(invalidPrefix)) {
            suffix = message.substring(invalidPrefix.length)
            isInvalidFields = false
            val cleaned = suffix.replace(Regex("[\\[\\]'\"]"), "").trim()
            if (cleaned.contains(" ")) {
                return message
            }
        } else {
            return message
        }
        
        val regex = Regex("[a-zA-Z0-9_]+")
        val tokens = regex.findAll(suffix).map { it.value }.toList()
        if (tokens.isEmpty()) {
            return if (isInvalidFields) "Some fields are incorrect" else message
        }

        val friendlyNames = mutableListOf<String>()
        for (token in tokens) {
            val upperToken = token.uppercase()
            val name = tokenMap[upperToken] ?: run {
                val parts = token.split("_")
                parts.mapIndexed { index, part ->
                    val partLower = part.lowercase()
                    if (index == 0) {
                        partLower.replaceFirstChar { it.uppercase() }
                    } else {
                        partLower
                    }
                }.joinToString(" ")
            }
            if (name.isNotEmpty() && !friendlyNames.contains(name)) {
                friendlyNames.add(name)
            }
        }
        
        if (friendlyNames.isEmpty()) {
            return if (isInvalidFields) "Some fields are incorrect" else message
        }
        
        return when (friendlyNames.size) {
            1 -> "${friendlyNames[0]} is incorrect"
            2 -> "${friendlyNames[0]} and ${friendlyNames[1]} are incorrect"
            else -> {
                val list = friendlyNames.dropLast(1).joinToString(", ")
                "$list, and ${friendlyNames.last()} are incorrect"
            }
        }
    }
}
