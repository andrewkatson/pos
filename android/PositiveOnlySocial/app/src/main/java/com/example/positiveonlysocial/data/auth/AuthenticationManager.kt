package com.example.positiveonlysocial.data.auth

import android.util.Log
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.data.model.AcceptPoliciesRequest
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

private const val TAG = "AuthenticationManager"

/**
 * Thrown by [AuthenticationManager.login] when a freshly issued session could not
 * be written to secure storage (issue #503).
 *
 * Screens read the session back out of the keychain rather than from memory, so a
 * session that was never persisted can't load anything. Swallowing the failure
 * put the user inside a signed-in shell where every screen rendered blank; the
 * caller must keep them on the login screen and say what happened instead.
 */
class SessionPersistenceException(cause: Throwable) :
    Exception(Constants.SESSION_STORAGE_FAILED_MESSAGE, cause)

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

    // Backing property for forcedLogout
    private val _forcedLogout = MutableStateFlow(false)
    /**
     * Set when the session was dropped without the user asking (the backend
     * revoked it, e.g. an account ban). The navigation layer observes this to
     * send the user back to the welcome screen from wherever they are.
     */
    val forcedLogout: StateFlow<Boolean> = _forcedLogout.asStateFlow()

    // Backing property for needsPrivacyPolicyAcceptance
    private val _needsPrivacyPolicyAcceptance = MutableStateFlow(false)
    /**
     * Whether the signed-in user still has to accept the privacy policy before
     * using the app (issue #620). Drives the re-accept dialog.
     *
     * Every opening of the app while signed in, and every fresh login, starts a
     * check ([isCheckingPrivacyPolicyAcceptance]): [checkPrivacyPolicyAcceptance]
     * asks the backend which version the user last accepted, and this only turns
     * true when that is missing or older than [Constants.POLICY_VERSION] — or
     * when the check fails, since asking is the safe answer. Accepting records
     * the bundled version on the backend ([recordPrivacyPolicyAcceptance]).
     */
    val needsPrivacyPolicyAcceptance: StateFlow<Boolean> = _needsPrivacyPolicyAcceptance.asStateFlow()

    // Backing property for isCheckingPrivacyPolicyAcceptance
    private val _isCheckingPrivacyPolicyAcceptance = MutableStateFlow(false)
    /**
     * True from a login (or an opening of the app while signed in) until the
     * backend has said whether the user still has to accept the privacy policy
     * (issue #620). Shared links and notification taps wait on it too.
     */
    val isCheckingPrivacyPolicyAcceptance: StateFlow<Boolean> =
        _isCheckingPrivacyPolicyAcceptance.asStateFlow()

    // Bumped by every new check and every logout, so a check still in flight
    // for an earlier session or opening can't settle the next one.
    @Volatile
    private var privacyPolicyCheckGeneration = 0

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
                // Opening the app with a saved session checks again (#620).
                startPrivacyPolicyCheck()
            } else {
                // No session object found
                _session.value = null
                _isLoggedIn.value = false
            }
        } catch (e: Exception) {
            // Handle errors (e.g., decryption failure, I/O error)
            Log.e(TAG, "Failed to load initial state", e)
            _session.value = null
            _isLoggedIn.value = false
        }
    }

    /**
     * Call this after your API login call succeeds.
     * This function is 'suspend' as it performs secure disk I/O.
     *
     * @param sessionData The new session to save and publish.
     * @throws SessionPersistenceException if the session could not be written to
     * secure storage. The manager stays logged out in that case, because a
     * session only this object knows about is one no screen can load with.
     *
     * A failed write clears [session] and [isLoggedIn] rather than leaving them
     * untouched, which matters if this is ever used to refresh a live session
     * rather than to establish a first one. Holding "logged in" while the store
     * that every screen reads from has just refused a write is the precise state
     * issue #503 was: signed-in shell, nothing behind it. Whatever was in the
     * keychain before is not a fallback — when the store is unopenable it can't
     * be read either, and no screen consults this object's copy.
     *
     * @param keepPrivacyPolicyAcceptance Pass true only when updating the session
     * of a user who is already signed in and using the app (identity
     * verification rewrites it in place), so they aren't asked to accept the
     * privacy policy again mid-session (#620), or when rotating the session of
     * one the app opening already asked ([onAppOpened]). Every other login asks.
     */
    suspend fun login(sessionData: UserSession, keepPrivacyPolicyAcceptance: Boolean = false) {
        // Use mutex.withLock to ensure atomic operation
        mutex.withLock {
            try {
                // Save the entire session object to secure storage
                keychainHelper.save(
                    sessionData,
                    service = keychainService,
                    account = sessionAccount
                )
            } catch (e: CancellationException) {
                // A cancelled login is not a failed one. Without this, the catch
                // below would rewrite it as a SessionPersistenceException, which
                // the login screen shows to the user as "we couldn't save your
                // login" — a report of something that never happened. Not
                // reachable while the only call in the try is a blocking write,
                // but this is a suspend function, so anything suspending added
                // in here later would make it so silently.
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "Failed to save session", e)
                _session.value = null
                _isLoggedIn.value = false
                throw SessionPersistenceException(e)
            }

            // Signing in, or being signed in automatically when the app opens,
            // checks the privacy policy acceptance (#620). This deliberately
            // doesn't look at isLoggedIn: this manager is a process-wide
            // singleton, so it can still read "logged in" when the app is
            // reopened in a process that outlived its Activity.
            if (!keepPrivacyPolicyAcceptance || !_isLoggedIn.value) {
                startPrivacyPolicyCheck()
            }

            // Publish the new session and state
            _session.value = sessionData
            _isLoggedIn.value = true
        }
    }

    // Whether an Activity has been created in this process yet.
    private var activityCreatedInThisProcess = false

    /**
     * Called from MainActivity.onCreate, before anything renders, so the
     * privacy-policy prompt (#620) covers every way the app can open:
     *
     * - A fresh launch ([restoringState] false) is an opening. A user still
     *   signed in — this manager outlives Activities in a surviving process —
     *   has to accept again.
     * - The first Activity in a new process restoring saved state is Android
     *   bringing the app back after killing it. The restored screens read the
     *   saved session from storage, but this new manager starts signed out, so
     *   load that session — which also asks for acceptance.
     * - Any later restore in the same process is a configuration change and
     *   leaves everything as it is.
     */
    fun onActivityCreated(restoringState: Boolean) {
        if (!restoringState) {
            onAppOpened()
        } else if (!activityCreatedInThisProcess) {
            checkInitialState()
        }
        activityCreatedInThisProcess = true
    }

    /**
     * The app was opened while possibly still signed in: check that user's
     * privacy policy acceptance again for this opening (#620).
     */
    fun onAppOpened() {
        if (_isLoggedIn.value) {
            startPrivacyPolicyCheck()
        }
    }

    private fun startPrivacyPolicyCheck() {
        privacyPolicyCheckGeneration += 1
        _needsPrivacyPolicyAcceptance.value = false
        _isCheckingPrivacyPolicyAcceptance.value = true
    }

    /**
     * Asks the backend which privacy policy version the signed-in user last
     * accepted (GET me/) and settles the pending check (#620): the dialog only
     * comes up when that is missing or older than [Constants.POLICY_VERSION], or
     * when the request fails. Does nothing when no check is pending.
     */
    suspend fun checkPrivacyPolicyAcceptance(api: PositiveOnlySocialAPI) {
        if (!_isCheckingPrivacyPolicyAcceptance.value) return
        val token = _session.value?.sessionToken ?: return
        val generation = privacyPolicyCheckGeneration
        val acceptedVersion = try {
            val response = api.getCurrentUser(token)
            if (response.isSuccessful) response.body()?.policiesAcceptedVersion else null
        } catch (e: CancellationException) {
            // Cancelled, not failed: leave the check pending for the next try.
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Privacy policy acceptance check failed", e)
            null
        }
        if (generation != privacyPolicyCheckGeneration || !_isCheckingPrivacyPolicyAcceptance.value) return
        _isCheckingPrivacyPolicyAcceptance.value = false
        _needsPrivacyPolicyAcceptance.value = !isPolicyVersionCurrent(acceptedVersion)
    }

    /**
     * Records, for this session, that the signed-in user accepted the privacy
     * policy (#620). Also used right after the Google consent dialog, whose
     * sign-up the backend already records.
     */
    fun acceptPrivacyPolicy() {
        privacyPolicyCheckGeneration += 1
        _isCheckingPrivacyPolicyAcceptance.value = false
        _needsPrivacyPolicyAcceptance.value = false
    }

    /**
     * Records on the backend that the user holding [sessionToken] accepted the
     * re-accept dialog, with the version this build bundles (#620). Best-effort,
     * like logout: if it fails they are simply asked again next time. Returns
     * whether it was recorded.
     */
    suspend fun recordPrivacyPolicyAcceptance(api: PositiveOnlySocialAPI, sessionToken: String): Boolean {
        return try {
            val response = api.acceptPolicies(sessionToken, AcceptPoliciesRequest(Constants.POLICY_VERSION))
            if (!response.isSuccessful) Log.w(TAG, "Recording privacy policy acceptance failed: ${response.code()}")
            response.isSuccessful
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "Recording privacy policy acceptance failed", e)
            false
        }
    }

    /**
     * Call this to log the user out.
     * This function is 'suspend' as it performs secure disk I/O.
     */
    suspend fun logout() {
        // Drop the prompt before waiting on the lock: logging out is also how
        // the user declines the policy, and the dialog should close at once
        // rather than linger until the session is cleared.
        privacyPolicyCheckGeneration += 1
        _isCheckingPrivacyPolicyAcceptance.value = false
        _needsPrivacyPolicyAcceptance.value = false

        // Use mutex.withLock to ensure atomic operation
        mutex.withLock {
            logoutCallCount += 1

            try {
                // Delete the session from secure storage
                keychainHelper.delete(keychainService, sessionAccount)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to delete session", e)
                // Even if delete fails, we log out from the app's state
            }

            // Clear the published properties
            _session.value = null
            _isLoggedIn.value = false
        }
    }

    /**
     * Logs out because the backend revoked the session (e.g. the account was
     * banned). Raises [forcedLogout] so the UI can navigate away.
     */
    suspend fun forceLogout() {
        logout()
        _forcedLogout.value = true
    }

    /**
     * Call after the UI has reacted to [forcedLogout].
     */
    fun clearForcedLogout() {
        _forcedLogout.value = false
    }

    companion object {
        /**
         * Whether a version on record covers the one this build shows. Versions
         * are `YYYY-MM-DD` dates, so they compare as strings; someone who
         * accepted a newer copy on a more up-to-date client isn't asked about
         * this one (#620).
         */
        fun isPolicyVersionCurrent(
            acceptedVersion: String?,
            bundledVersion: String = Constants.POLICY_VERSION
        ): Boolean = acceptedVersion != null && acceptedVersion >= bundledVersion
    }
}
