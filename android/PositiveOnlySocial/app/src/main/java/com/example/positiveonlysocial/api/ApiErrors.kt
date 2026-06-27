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
        return backendError ?: statusMessage(response.code(), fallback)
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
}
