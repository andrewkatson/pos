package com.example.positiveonlysocial.data.auth

import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Manages the user's authentication state and session data.
 *
 * This is the Kotlin equivalent of your Swift AuthenticationManager.
 * It uses StateFlow to expose the auth state to the UI (Jetpack Compose).
 *
 * This class should be treated as a singleton in your application (e.g., created
 * once in your Application class or injected with Hilt).
 *
 * @param keychainHelper An instance of your secure storage implementation.
 * @param shouldAutoLogin If true, the manager will try to load a session from
 * storage immediately upon creation.
 */
class AuthenticationManager(
    private val keychainHelper: KeychainHelperProtocol,
    shouldAutoLogin: Boolean = false
) {

    // --- Public StateFlow Properties (Equivalent to @Published) ---

    // Backing property for isLoggedIn
    private val _isLoggedIn = MutableStateFlow(false)
    /**
     * Public, read-only StateFlow for the UI to observe login state.
     */
    val isLoggedIn: StateFlow<Boolean> = _isLoggedIn.asStateFlow()

    // Backing property for session
    private val _session = MutableStateFlow<UserSession?>(null)
    /**
     * Public, read-only StateFlow for the UI to observe the session.
     */
    val session: StateFlow<UserSession?> = _session.asStateFlow()

    // --- Private Properties ---

    // Identifiers for secure storage
    private val keychainService = "positive-only-social.Positive-Only-Social"
    private val sessionAccount = "userSessionToken"

    // A coroutine-based Mutex to replicate NSLock for thread-safety.
    // This ensures login() and logout() cannot run at the same time.
    private val mutex = Mutex()

    // Property for testing
    var logoutCallCount = 0
        private set // Makes the 'setter' private

    /**
     * Automatically checks for a saved session upon initialization.
     */
    init {
        if (shouldAutoLogin) {
            checkInitialState()
        } else {
            // Explicitly set to logged out
            _session.value = null
            _isLoggedIn.value = false
        }
    }

    /**
     * Tries to load a UserSession from secure storage.
     */
    private fun checkInitialState() {
        try {
            // Try to load the entire session object
            val loadedSession = keychainHelper.load(
                UserSession::class.java, // Use .java to get the Class type
                service = keychainService,
                account = sessionAccount
            )

            if (loadedSession != null) {
                // We're logged in, publish the session
                _session.value = loadedSession
                _isLoggedIn.value = true
            } else {
                // No session object found
                _session.value = null
                _isLoggedIn.value = false
            }
        } catch (e: Exception) {
            // Handle errors (e.g., decryption failure, I/O error)
            println("Failed to load initial state: $e")
            _session.value = null
            _isLoggedIn.value = false
        }
    }

    /**
     * Call this after your API login call succeeds.
     * This function is 'suspend' as it performs secure disk I/O.
     *
     * @param sessionData The new session to save and publish.
     */
    suspend fun login(sessionData: UserSession) {
        // Use mutex.withLock to ensure atomic operation
        mutex.withLock {
            try {
                // Save the entire session object to secure storage
                keychainHelper.save(
                    sessionData,
                    service = keychainService,
                    account = sessionAccount
                )

                // Publish the new session and state
                _session.value = sessionData
                _isLoggedIn.value = true

            } catch (e: Exception) {
                println("Failed to save session: $e")
                // Here you might want to propagate the error
            }
        }
    }

    /**
     * Call this to log the user out.
     * This function is 'suspend' as it performs secure disk I/O.
     */
    suspend fun logout() {
        // Use mutex.withLock to ensure atomic operation
        mutex.withLock {
            logoutCallCount += 1

            try {
                // Delete the session from secure storage
                keychainHelper.delete(keychainService, sessionAccount)
            } catch (e: Exception) {
                println("Failed to delete session: $e")
                // Even if delete fails, we log out from the app's state
            }

            // Clear the published properties
            _session.value = null
            _isLoggedIn.value = false
        }
    }
}