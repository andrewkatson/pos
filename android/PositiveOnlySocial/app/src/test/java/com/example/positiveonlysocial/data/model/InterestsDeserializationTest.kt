package com.example.positiveonlysocial.data.model

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Locks in the JSON mapping for the positive-interest endpoints (issues
 * #446/#35). New response list fields are nullable so a partial/older payload
 * deserializes rather than crashing (Gson does not apply Kotlin defaults for
 * absent JSON); callers read via `.orEmpty()`.
 */
class InterestsDeserializationTest {

    private val gson = Gson()

    @Test
    fun `options json maps slug and name`() {
        val json = """{"options": [{"slug": "nature", "name": "Nature"}]}"""
        val response = gson.fromJson(json, InterestOptionsResponse::class.java)
        assertEquals(1, response.options?.size)
        assertEquals("nature", response.options?.first()?.slug)
        assertEquals("Nature", response.options?.first()?.name)
    }

    @Test
    fun `set-interests json maps categories, accepted and rejected`() {
        val json = """
            {
              "categories": ["nature"],
              "freeform": {
                "accepted": ["music"],
                "rejected": [{"text": "bad", "reason_code": "guidelines", "reason": "nope"}]
              },
              "message": "ok"
            }
        """.trimIndent()
        val response = gson.fromJson(json, SetInterestsResponse::class.java)
        assertEquals(listOf("nature"), response.categories)
        assertEquals(listOf("music"), response.freeform?.accepted)
        assertEquals("bad", response.freeform?.rejected?.first()?.text)
        assertEquals("guidelines", response.freeform?.rejected?.first()?.reasonCode)
        assertEquals("ok", response.message)
    }

    @Test
    fun `interests json from an older server without fields parses to null`() {
        val response = gson.fromJson("{}", InterestsResponse::class.java)
        assertNull(response.categories)
        assertNull(response.freeform)
        // Callers read via orEmpty().
        assertTrue(response.categories.orEmpty().isEmpty())
    }
}
