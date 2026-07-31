package com.example.positiveonlysocial.models.viewmodels

import com.example.positiveonlysocial.MainDispatcherRule
import com.example.positiveonlysocial.api.StatefulStubbedAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.model.RegisterRequest
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever

/**
 * Exercises the SettingsViewModel interest flow (issues #446/#35) against the
 * in-memory stub. The stub reproduces the backend's TESTING classifier (reject
 * anything containing "negative") and keyword-maps freeform terms to buckets, so
 * these tests drive accept/reject/mapping/removal end to end.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class SettingsViewModelInterestsTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private suspend fun buildViewModelFor(api: StatefulStubbedAPI, username: String): SettingsViewModel {
        val auth = api.register(
            RegisterRequest(username, "$username@test.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!
        val session = UserSession(auth.sessionToken, username, auth.userId!!, false, null, null)
        val keychain: KeychainHelperProtocol = mock()
        whenever(keychain.load(any<Class<UserSession>>(), any(), any())).thenReturn(session)
        val authManager: AuthenticationManager = mock()
        return SettingsViewModel(api, authManager, keychain)
    }

    @Test
    fun `loadInterests prefills options and empty selection`() = runTest {
        val api = StatefulStubbedAPI()
        val vm = buildViewModelFor(api, "ada")
        vm.loadInterests()
        advanceUntilIdle()
        assertTrue(vm.interestOptions.value.isNotEmpty())
        assertTrue(vm.interestOptions.value.any { it.slug == "nature" })
        assertTrue(vm.selectedInterestSlugs.value.isEmpty())
        assertTrue(vm.freeformInterests.value.isEmpty())
    }

    @Test
    fun `saveInterests applies picks and mapped freeform`() = runTest {
        val api = StatefulStubbedAPI()
        val vm = buildViewModelFor(api, "grace")
        vm.toggleInterest("nature")
        vm.addFreeformInterests(listOf("music", "hiking"))
        vm.saveInterests()
        advanceUntilIdle()

        assertTrue(vm.rejectedInterests.value.isEmpty())
        assertTrue(vm.interestsSaved.value)
        // "hiking" is kept but maps to no bucket; "music" maps to the music bucket.
        assertEquals(listOf("music", "hiking"), vm.freeformInterests.value)
    }

    @Test
    fun `saveInterests then reload reflects the union for the same user`() = runTest {
        val api = StatefulStubbedAPI()
        // Register once; keep the same session/account for both VMs.
        val auth = api.register(
            RegisterRequest("hopper", "hopper@test.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!
        val session = UserSession(auth.sessionToken, "hopper", auth.userId!!, false, null, null)
        val keychain: KeychainHelperProtocol = mock()
        whenever(keychain.load(any<Class<UserSession>>(), any(), any())).thenReturn(session)
        val vm = SettingsViewModel(api, mock<AuthenticationManager>(), keychain)

        vm.toggleInterest("nature")
        vm.addFreeformInterests(listOf("music"))
        vm.saveInterests()
        advanceUntilIdle()

        val reload = SettingsViewModel(api, mock<AuthenticationManager>(), keychain)
        reload.loadInterests()
        advanceUntilIdle()
        assertEquals(setOf("music", "nature"), reload.selectedInterestSlugs.value.toSet())
    }

    @Test
    fun `saveInterests rejects disallowed freeform`() = runTest {
        val api = StatefulStubbedAPI()
        val vm = buildViewModelFor(api, "curie")
        vm.addFreeformInterests(listOf("negative energy"))
        vm.saveInterests()
        advanceUntilIdle()
        assertEquals(1, vm.rejectedInterests.value.size)
        assertFalse(vm.interestsSaved.value)
        assertTrue(vm.freeformInterests.value.isEmpty())
    }

    @Test
    fun `deselecting a bucket removes it on save`() = runTest {
        val api = StatefulStubbedAPI()
        val auth = api.register(
            RegisterRequest("lovelace", "lovelace@test.com", "pw12345", "false", "127.0.0.1", "1970-01-01")
        ).body()!!
        val session = UserSession(auth.sessionToken, "lovelace", auth.userId!!, false, null, null)
        val keychain: KeychainHelperProtocol = mock()
        whenever(keychain.load(any<Class<UserSession>>(), any(), any())).thenReturn(session)
        val vm = SettingsViewModel(api, mock<AuthenticationManager>(), keychain)

        vm.toggleInterest("nature")
        vm.toggleInterest("music")
        vm.saveInterests()
        advanceUntilIdle()

        vm.toggleInterest("nature") // deselect
        vm.saveInterests()
        advanceUntilIdle()

        val reload = SettingsViewModel(api, mock<AuthenticationManager>(), keychain)
        reload.loadInterests()
        advanceUntilIdle()
        assertEquals(listOf("music"), reload.selectedInterestSlugs.value)
    }
}
