package com.example.positiveonlysocial.data

import com.example.positiveonlysocial.data.constants.Constants
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The terms of service shipped in the app (issue #493). */
class TermsOfServiceTest {

    @Test
    fun everySectionCarriesTextToShow() {
        assertTrue(Constants.TERMS_OF_SERVICE_SECTIONS.isNotEmpty())
        Constants.TERMS_OF_SERVICE_SECTIONS.forEach { section ->
            assertTrue(section.heading.isNotBlank())
            assertTrue(section.body.isNotBlank())
        }
        assertTrue(Constants.TERMS_OF_SERVICE_LAST_UPDATED.isNotBlank())
    }

    @Test
    fun headingsAreUnique() {
        val headings = Constants.TERMS_OF_SERVICE_SECTIONS.map { it.heading }
        assertEquals(headings.size, headings.toSet().size)
    }

    @Test
    fun saysWhatSigningInWithGoogleShares() {
        // Google's OAuth consent screen links to these terms, so the Google
        // section has to ship in the app too, not only on the website.
        val google = Constants.TERMS_OF_SERVICE_SECTIONS
            .firstOrNull { it.heading == "Signing in with Google" }
        assertNotNull(google)
        assertTrue(google!!.body.contains("verified email address"))
    }
}
