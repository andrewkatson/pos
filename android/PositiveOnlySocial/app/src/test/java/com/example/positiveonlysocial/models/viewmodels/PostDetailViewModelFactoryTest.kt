package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.mock

class PostDetailViewModelFactoryTest {

    @Test
    fun `create returns PostDetailViewModel`() {
        val api = mock<PositiveOnlySocialAPI>()
        val keychainHelper = mock<KeychainHelperProtocol>()
        val factory = PostDetailViewModelFactory("post1", api, keychainHelper)

        val viewModel = factory.create(PostDetailViewModel::class.java)

        assertNotNull(viewModel)
        assertTrue(viewModel is PostDetailViewModel)
    }
}
