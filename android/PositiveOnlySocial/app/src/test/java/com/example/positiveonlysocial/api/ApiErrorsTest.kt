package com.example.positiveonlysocial.api

import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Response
import java.net.SocketTimeoutException
import java.net.UnknownHostException

/**
 * Locks in the user-facing error mapping. The backend's own `{"error": ...}`
 * copy is passed through, but a gateway timeout or routing failure (which
 * returns HTML or nothing) must surface as plain language — never a raw status
 * code, raw body, or low-level exception message.
 */
class ApiErrorsTest {

    private fun errorResponse(code: Int, body: String): Response<Any> =
        Response.error(code, body.toResponseBody("application/json".toMediaTypeOrNull()))

    @Test
    fun `backend error message is passed through`() {
        val response = errorResponse(400, """{"error":"Text is not positive"}""")
        assertEquals(
            "Text is not positive",
            ApiErrors.messageFor(response, fallback = "fallback")
        )
    }

    @Test
    fun `gateway timeout maps to friendly text without status code`() {
        val response = errorResponse(504, "<html><body>504 Gateway Time-out</body></html>")
        val message = ApiErrors.messageFor(response, fallback = "fallback")
        assertEquals(
            "The server is taking too long to respond. Please try again in a moment.",
            message
        )
        assertFalse(message.contains("504"))
    }

    @Test
    fun `not found maps to friendly text without status code`() {
        val message = ApiErrors.messageFor(errorResponse(404, ""), fallback = "fallback")
        assertFalse(message.contains("404"))
        assertTrue(message.isNotBlank())
    }

    @Test
    fun `rate limited maps to friendly text`() {
        assertEquals(
            "You're doing that too often. Please wait a moment and try again.",
            ApiErrors.messageFor(errorResponse(429, ""), fallback = "fallback")
        )
    }

    @Test
    fun `unmapped status falls back`() {
        assertEquals(
            "fallback",
            ApiErrors.messageFor(errorResponse(418, "not json"), fallback = "fallback")
        )
    }

    @Test
    fun `socket timeout maps to friendly text`() {
        assertEquals(
            "The request timed out. Please check your connection and try again.",
            ApiErrors.messageFor(SocketTimeoutException(), fallback = "fallback")
        )
    }

    @Test
    fun `unknown host maps to friendly text`() {
        assertEquals(
            "We couldn't reach the server. Please check your connection and try again.",
            ApiErrors.messageFor(UnknownHostException(), fallback = "fallback")
        )
    }

    @Test
    fun `unknown throwable falls back`() {
        assertEquals(
            "fallback",
            ApiErrors.messageFor(IllegalStateException("boom"), fallback = "fallback")
        )
    }

    @Test
    fun `sanitizeErrorMessage handles unrelated error messages`() {
        assertEquals("Text is not positive", ApiErrors.sanitizeErrorMessage("Text is not positive"))
        assertEquals("User already exists", ApiErrors.sanitizeErrorMessage("User already exists"))
    }

    @Test
    fun `sanitizeErrorMessage handles single token invalid fields`() {
        assertEquals("Username is incorrect", ApiErrors.sanitizeErrorMessage("Invalid fields ['USERNAME']"))
        assertEquals("Password is incorrect", ApiErrors.sanitizeErrorMessage("Invalid fields ['PASSWORD']"))
    }

    @Test
    fun `sanitizeErrorMessage handles multiple token invalid fields`() {
        assertEquals(
            "Username and Password are incorrect",
            ApiErrors.sanitizeErrorMessage("Invalid fields ['USERNAME', 'PASSWORD']")
        )
        assertEquals(
            "Username, Password, and Email are incorrect",
            ApiErrors.sanitizeErrorMessage("Invalid fields ['USERNAME', 'PASSWORD', 'EMAIL']")
        )
    }

    @Test
    fun `sanitizeErrorMessage handles single token without brackets`() {
        assertEquals("Post identifier is incorrect", ApiErrors.sanitizeErrorMessage("Invalid post_identifier"))
        assertEquals("Target type is incorrect", ApiErrors.sanitizeErrorMessage("Invalid target_type"))
    }

    @Test
    fun `sanitizeErrorMessage leaves human-readable invalid messages untouched`() {
        assertEquals("Invalid comment text", ApiErrors.sanitizeErrorMessage("Invalid comment text"))
        assertEquals("Invalid batch parameter", ApiErrors.sanitizeErrorMessage("Invalid batch parameter"))
    }
}
