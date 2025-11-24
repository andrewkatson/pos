package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.mock

class ProfileViewModelFactoryTest {

    @Test
    fun `create returns ProfileViewModel`() {
        val api = mock<PositiveOnlySocialAPI>()
        val keychainHelper = mock<KeychainHelperProtocol>()
        val factory = ProfileViewModelFactory(api, keychainHelper)

        val viewModel = factory.create(ProfileViewModel::class.java)

        assertNotNull(viewModel)
        assertTrue(viewModel is ProfileViewModel)
    }
}
