package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.mock

class FeedViewModelFactoryTest {

    @Test
    fun `create returns FeedViewModel`() {
        val api = mock<PositiveOnlySocialAPI>()
        val keychainHelper = mock<KeychainHelperProtocol>()
        val factory = FeedViewModelFactory(api, keychainHelper)

        val viewModel = factory.create(FeedViewModel::class.java)

        assertNotNull(viewModel)
        assertTrue(viewModel is FeedViewModel)
    }

    @Test(expected = IllegalArgumentException::class)
    fun `create throws exception for unknown class`() {
        val api = mock<PositiveOnlySocialAPI>()
        val keychainHelper = mock<KeychainHelperProtocol>()
        val factory = FeedViewModelFactory(api, keychainHelper)

        factory.create(HomeViewModel::class.java)
    }
}
