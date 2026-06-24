package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.GenericResponse
import com.example.positiveonlysocial.data.model.HiddenComment
import com.example.positiveonlysocial.data.model.HiddenPost
import com.example.positiveonlysocial.data.model.MyAppeal
import com.example.positiveonlysocial.data.model.SubmitAppealRequest
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.google.gson.Gson
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.Response

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
    private val gson = Gson()

    fun clearError() {
        _errorMessage.value = null
    }

    private fun session(): UserSession? =
        keychainHelper.load(UserSession::class.java, service, account)

    /**
     * Extracts the backend's `error` message from a failed response body so the
     * UI shows the message rather than the raw `{"error": ...}` JSON.
     */
    private fun errorOf(response: Response<*>): String {
        val raw = response.errorBody()?.string()
        return try {
            gson.fromJson(raw, GenericResponse::class.java)?.error ?: raw ?: "Request failed"
        } catch (e: Exception) {
            raw ?: "Request failed"
        }
    }

    /** Loads (or reloads) the first page of hidden content and filed appeals. */
    fun load() {
        _isLoading.value = true
        _errorMessage.value = null // drop any stale error from a previous load/submit
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
                    _errorMessage.value = errorOf(postsResp)
                }

                val commentsResp = api.getHiddenComments(token, 0)
                if (commentsResp.isSuccessful) {
                    _hiddenComments.value = commentsResp.body() ?: emptyList()
                } else {
                    _errorMessage.value = errorOf(commentsResp)
                }

                val appealsResp = api.getMyAppeals(token, 0)
                if (appealsResp.isSuccessful) {
                    _appeals.value = appealsResp.body() ?: emptyList()
                } else {
                    _errorMessage.value = errorOf(appealsResp)
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
                    _errorMessage.value = errorOf(response)
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
