package com.example.positiveonlysocial.api

import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class APIProviderTest {

    @After
    fun tearDown() {
        APIProvider.resetService()
    }

    @Test
    fun `normal app configuration uses real API`() {
        val api = APIProvider.returnGoodVibesOnlyAPI(
            baseUrl = "https://example.com/",
            isUITesting = false
        )

        assertFalse(api is StatefulStubbedAPI)
    }

    @Test
    fun `explicit UI test configuration uses stub API`() {
        val api = APIProvider.returnGoodVibesOnlyAPI(
            baseUrl = "https://example.com/",
            isUITesting = true
        )

        assertTrue(api is StatefulStubbedAPI)
    }
}