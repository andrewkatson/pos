package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.mock

class SettingsViewModelFactoryTest {

    @Test
    fun `create returns SettingsViewModel`() {
        val api = mock<PositiveOnlySocialAPI>()
        val authManager = mock<AuthenticationManager>()
        val keychainHelper = mock<KeychainHelperProtocol>()
        val factory = SettingsViewModelFactory(api, authManager, keychainHelper)

        val viewModel = factory.create(SettingsViewModel::class.java)

        assertNotNull(viewModel)
        assertTrue(viewModel is SettingsViewModel)
    }
}
