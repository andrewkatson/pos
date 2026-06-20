package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.HiddenComment
import com.example.positiveonlysocial.data.model.HiddenPost
import com.example.positiveonlysocial.data.model.MyAppeal
import com.example.positiveonlysocial.data.model.SubmitAppealRequest
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

private const val TAG = "AppealsViewModel"

/**
 * Loads the signed-in user's hidden posts/comments and the appeals they have
 * filed, and submits new content appeals. Ban appeals are not here — those go
 * through the suspension email (an outright-banned user has no session).
 */
class AppealsViewModel(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken"
) : ViewModel() {

    private val _hiddenPosts = MutableStateFlow<List<HiddenPost>>(emptyList())
    val hiddenPosts: StateFlow<List<HiddenPost>> = _hiddenPosts.asStateFlow()

    private val _hiddenComments = MutableStateFlow<List<HiddenComment>>(emptyList())
    val hiddenComments: StateFlow<List<HiddenComment>> = _hiddenComments.asStateFlow()

    private val _appeals = MutableStateFlow<List<MyAppeal>>(emptyList())
    val appeals: StateFlow<List<MyAppeal>> = _appeals.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    private val service = "positive-only-social.Positive-Only-Social"

    fun clearError() {
        _errorMessage.value = null
    }

    private fun session(): UserSession? =
        keychainHelper.load(UserSession::class.java, service, account)

    /** Loads (or reloads) the first page of hidden content and filed appeals. */
    fun load() {
        _isLoading.value = true
        viewModelScope.launch {
            try {
                val userSession = session()
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot load appeals")
                    return@launch
                }
                val token = userSession.sessionToken

                val postsResp = api.getHiddenPosts(token, 0)
                if (postsResp.isSuccessful) {
                    _hiddenPosts.value = postsResp.body() ?: emptyList()
                } else {
                    _errorMessage.value = postsResp.errorBody()?.string()
                }

                val commentsResp = api.getHiddenComments(token, 0)
                if (commentsResp.isSuccessful) {
                    _hiddenComments.value = commentsResp.body() ?: emptyList()
                }

                val appealsResp = api.getMyAppeals(token, 0)
                if (appealsResp.isSuccessful) {
                    _appeals.value = appealsResp.body() ?: emptyList()
                }
            } catch (e: Exception) {
                _errorMessage.value = e.localizedMessage
                Log.e(TAG, "Error loading appeals", e)
            } finally {
                _isLoading.value = false
            }
        }
    }

    /**
     * Files an appeal for a hidden post or comment. `targetType` is "post" or
     * "comment". Reloads on success and reports the outcome via [onResult].
     */
    fun submitAppeal(
        targetType: String,
        targetIdentifier: String,
        reason: String,
        onResult: (Boolean) -> Unit = {}
    ) {
        viewModelScope.launch {
            try {
                val userSession = session()
                if (userSession == null) {
                    onResult(false)
                    return@launch
                }
                val response = api.submitAppeal(
                    userSession.sessionToken,
                    SubmitAppealRequest(targetType, targetIdentifier, reason)
                )
                if (response.isSuccessful) {
                    load()
                    onResult(true)
                } else {
                    _errorMessage.value = response.errorBody()?.string()
                    onResult(false)
                }
            } catch (e: Exception) {
                _errorMessage.value = e.localizedMessage
                Log.e(TAG, "Error submitting appeal", e)
                onResult(false)
            }
        }
    }
}
