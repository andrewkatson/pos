package com.example.positiveonlysocial.models.viewmodels

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.Post
import com.example.positiveonlysocial.data.model.ProfileDetailsResponse
import com.example.positiveonlysocial.data.model.SetProfilePhotoRequest
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.data.uploader.ImageUploader
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

private const val TAG = "ProfileViewModel"

class ProfileViewModel(
    private val api: PositiveOnlySocialAPI,
    private val keychainHelper: KeychainHelperProtocol,
    private val account: String = "userSessionToken",
    // Uploads the JPEG bytes to the presigned S3 URL. Defaulted to the real
    // ImageUploader (compress + EXIF-strip + PUT), and injectable so unit tests
    // can substitute a no-op — the real one decodes a Bitmap, which needs the
    // Android framework (issue #7).
    private val uploadBytes: suspend (ByteArray, String) -> Unit = { data, url ->
        ImageUploader().upload(data, url)
    }
) : ViewModel() {

    // Published properties
    private val _profileDetails = MutableStateFlow<ProfileDetailsResponse?>(null)
    val profileDetails: StateFlow<ProfileDetailsResponse?> = _profileDetails.asStateFlow()

    private val _userPosts = MutableStateFlow<List<Post>>(emptyList())
    val userPosts: StateFlow<List<Post>> = _userPosts.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _isFollowing = MutableStateFlow(false)
    val isFollowing: StateFlow<Boolean> = _isFollowing.asStateFlow()

    private val _isBlocked = MutableStateFlow(false)
    val isBlocked: StateFlow<Boolean> = _isBlocked.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    private val _isRefreshing = MutableStateFlow(false)
    val isRefreshing: StateFlow<Boolean> = _isRefreshing.asStateFlow()

    private val _isOwnProfile = MutableStateFlow(false)
    val isOwnProfile: StateFlow<Boolean> = _isOwnProfile.asStateFlow()

    // True while the owner's profile-photo set/remove is in flight (issue #7), so
    // the header can disable the controls and show a spinner.
    private val _isPhotoBusy = MutableStateFlow(false)
    val isPhotoBusy: StateFlow<Boolean> = _isPhotoBusy.asStateFlow()

    // Photo-specific error (issue #7), shown next to the photo controls in the
    // header rather than via the shared errorMessage (which the profile screen
    // uses for load failures). Covers the whole flow: reading the picked bytes,
    // the presigned upload, and the set/remove calls.
    private val _photoErrorMessage = MutableStateFlow<String?>(null)
    val photoErrorMessage: StateFlow<String?> = _photoErrorMessage.asStateFlow()

    /**
     * Like / report / retract-report / delete for the posts in this profile's
     * grid, so they can be acted on without opening each one (issue #267).
     * Deleting drops the post from [userPosts]; the Posts stat is rendered from
     * that list, so the count follows automatically.
     */
    val postActions = PostListActions(api, keychainHelper, viewModelScope, _userPosts, account)

    // Reconciling async post classification (issue #282): a short bounded poll
    // runs while any of the *viewer's own* posts is pending, then stops; the
    // ordinary mount/pull-to-refresh reload is the backstop after that. A
    // rejection surfaces once through `reviewNotice`.
    //
    // This lives here rather than in HomeViewModel because the Profile tab's
    // grid is this view model's (issue #347). Only your own posts ever carry a
    // status — everyone else's pending/hidden posts are filtered out
    // server-side — so a non-own profile simply never has anything to poll.
    private val _reviewNotice = MutableStateFlow<String?>(null)
    val reviewNotice: StateFlow<String?> = _reviewNotice.asStateFlow()

    private var statusPollJob: Job? = null
    private var statusPollAttempts = 0
    // ~30s of checks, 3s apart. Internal so tests can shorten the interval.
    var statusPollIntervalMs = 3000L
    private val statusPollMaxAttempts = 10
    /** At most this many pending posts are polled per round (see
     * startStatusPollIfNeeded for the rate-limit math). */
    private val statusPollMaxPosts = 3

    fun dismissReviewNotice() {
        _reviewNotice.value = null
    }

    private val service = "positive-only-social.Positive-Only-Social"

    // Pagination state
    private var currentPage = 0
    private var canLoadMore = true

    fun fetchProfile(username: String) {
        _isLoading.value = true
        _errorMessage.value = null

        // Reset pagination state when loading a new profile
        currentPage = 0
        canLoadMore = true
        _userPosts.value = emptyList() // Clear old posts immediately

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot fetch profile")
                    // Fail safe: without a session we can't claim this is the
                    // user's own profile, so don't leave a stale `true` that would
                    // wrongly hide Follow/Block on someone else's profile.
                    _isOwnProfile.value = false
                    return@launch
                }

                _isOwnProfile.value = (userSession.username == username)

                // Fetch Profile Details
                val profileResponse = api.getProfileDetails(userSession.sessionToken, username)
                if (profileResponse.isSuccessful) {
                    val profile = profileResponse.body()
                    _profileDetails.value = profile
                    _isFollowing.value = profile?.isFollowing ?: false
                    _isBlocked.value = profile?.isBlocked ?: false
                } else {
                    _errorMessage.value = ApiErrors.messageFor(profileResponse, fallback = "Failed to load this profile. Please try again.")
                }

                // Fetch Initial User Posts (Page 0)
                val postsResponse = api.getPostsForUser(userSession.sessionToken, username, 0)
                if (postsResponse.isSuccessful) {
                    val newPosts = postsResponse.body() ?: emptyList()
                    _userPosts.value = newPosts

                    if (newPosts.isEmpty()) {
                        canLoadMore = false
                    } else {
                        currentPage += 1
                    }
                } else {
                    if (_errorMessage.value == null) {
                        _errorMessage.value = ApiErrors.messageFor(postsResponse, fallback = "Failed to load posts. Please try again.")
                    }
                }

            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
                Log.e(TAG, "Error fetching profile", e)
            } finally {
                _isLoading.value = false
            }
        }
    }

    /**
     * Pull-to-refresh: resets pagination and reloads the profile's details and
     * posts from the first page, replacing the existing list with the freshest
     * posts from the backend.
     */
    fun refreshProfile(username: String) {
        // Don't refresh while a paginated fetch is in flight; they share
        // _userPosts/currentPage/canLoadMore and would otherwise race.
        if (_isRefreshing.value || _isLoading.value) return

        _isRefreshing.value = true
        _errorMessage.value = null

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot refresh profile")
                    return@launch
                }

                val profileResponse = api.getProfileDetails(userSession.sessionToken, username)
                if (profileResponse.isSuccessful) {
                    val profile = profileResponse.body()
                    _profileDetails.value = profile
                    _isFollowing.value = profile?.isFollowing ?: false
                    _isBlocked.value = profile?.isBlocked ?: false
                } else {
                    // Surface the failure instead of silently leaving follow/block
                    // state stale (mirrors fetchProfile()).
                    _errorMessage.value = ApiErrors.messageFor(profileResponse, fallback = "Failed to load this profile. Please try again.")
                }

                val postsResponse = api.getPostsForUser(userSession.sessionToken, username, 0)
                if (postsResponse.isSuccessful) {
                    val newPosts = postsResponse.body() ?: emptyList()
                    _userPosts.value = newPosts
                    canLoadMore = newPosts.isNotEmpty()
                    currentPage = if (newPosts.isEmpty()) 0 else 1
                    // A fresh first page grants a fresh reconcile-poll budget (#282).
                    statusPollAttempts = 0
                    startStatusPollIfNeeded()
                } else if (_errorMessage.value == null) {
                    _errorMessage.value = ApiErrors.messageFor(postsResponse, fallback = "Failed to load posts. Please try again.")
                }
            } catch (e: Exception) {
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
                Log.e(TAG, "Error refreshing profile", e)
            } finally {
                _isRefreshing.value = false
            }
        }
    }

    fun fetchUserPosts(username: String) {
        // Guard against multiple fetches, reaching the end, or racing a
        // pull-to-refresh (which resets the pagination cursor).
        if (_isLoading.value || _isRefreshing.value || !canLoadMore) return

        _isLoading.value = true

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot fetch posts")
                    return@launch
                }

                val response = api.getPostsForUser(userSession.sessionToken, username, currentPage)

                if (response.isSuccessful) {
                    val newPosts = response.body() ?: emptyList()

                    if (newPosts.isEmpty()) {
                        canLoadMore = false
                    } else {
                        // Append new posts to existing list
                        _userPosts.value += newPosts
                        currentPage += 1
                    }
                    startStatusPollIfNeeded()
                } else {
                    Log.e(TAG, "Failed to fetch more posts: ${response.errorBody()?.string()}")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error fetching more posts", e)
            } finally {
                _isLoading.value = false
            }
        }
    }

    /**
     * Starts (or continues) the short bounded status poll (#282) when any of
     * the viewer's own posts is still pending classification. No-op when
     * nothing is pending, a poll is already scheduled, or the budget is spent.
     */
    private fun startStatusPollIfNeeded() {
        // The grid is newest-first, so this polls the most recent pending
        // posts; the cap keeps the worst case (3 posts every 3s = 60
        // requests/min) inside the status endpoint's 120/m per-user rate
        // limit, and older pending posts reconcile on refresh.
        val pendingIds = _userPosts.value.filter { it.status == "pending" }
            .take(statusPollMaxPosts)
            .map { it.postIdentifier }
        if (pendingIds.isEmpty() || statusPollJob != null || statusPollAttempts >= statusPollMaxAttempts) return

        statusPollJob = viewModelScope.launch {
            delay(statusPollIntervalMs)
            // Clear before polling so the poll round itself can re-arm the
            // next round (directly or via the reload it triggers).
            statusPollJob = null
            statusPollAttempts += 1
            pollPendingStatuses(pendingIds)
        }
    }

    /**
     * One poll round (#282): check each pending post's status. When any has
     * resolved, reload the grid (approved posts lose their badge; final
     * rejections drop out) and surface a rejection notice; otherwise re-arm
     * the timer within the budget.
     */
    private suspend fun pollPendingStatuses(pendingIds: List<String>) {
        val userSession = keychainHelper.load(UserSession::class.java, service, account) ?: return

        var anyResolved = false
        for (postId in pendingIds) {
            try {
                val response = api.getPostStatus(userSession.sessionToken, postId)
                val body = response.body()
                if (response.isSuccessful && body != null && body.status != "pending") {
                    anyResolved = true
                    if (body.status == "rejected" || body.status == "rejected_final") {
                        _reviewNotice.value = body.message
                            ?: "One of your recent posts did not pass automated review."
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error polling post status for $postId", e)
            }
        }

        if (anyResolved) {
            refreshProfile(userSession.username)
        } else {
            startStatusPollIfNeeded()
        }
    }

    /**
     * Sets the signed-in user's profile photo (issue #7): uploads the JPEG bytes
     * via the same presigned pipeline post images use (createUploadUrl +
     * ImageUploader), hands the canonical URL to setProfilePhoto, then reloads
     * the profile so the header reflects the new pending/approved state. The
     * caller reads the picked photo's bytes (it needs a Context); the byte-free
     * upload + set + reload live here.
     */
    fun setProfilePhoto(username: String, imageBytes: ByteArray) {
        if (_isPhotoBusy.value) return
        _isPhotoBusy.value = true
        _photoErrorMessage.value = null

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot set profile photo")
                    _photoErrorMessage.value = "Not logged in."
                    return@launch
                }
                val token = userSession.sessionToken

                val uploadUrlResponse = api.createUploadUrl(token)
                val uploadUrlBody = uploadUrlResponse.body()
                if (!uploadUrlResponse.isSuccessful || uploadUrlBody == null) {
                    _photoErrorMessage.value = "Could not update your profile photo. Please try again."
                    return@launch
                }

                uploadBytes(imageBytes, uploadUrlBody.uploadUrl)

                val setResponse = api.setProfilePhoto(token, SetProfilePhotoRequest(uploadUrlBody.imageUrl))
                if (!setResponse.isSuccessful) {
                    _photoErrorMessage.value = ApiErrors.messageFor(setResponse, fallback = "Could not update your profile photo. Please try again.")
                    return@launch
                }

                // Reload so the header shows the new photo / review state. On
                // async backends it reads back as pending; the eager path and the
                // stub have already approved it.
                reloadProfileDetails(username, token)
            } catch (e: Exception) {
                Log.e(TAG, "Error setting profile photo", e)
                _photoErrorMessage.value = ApiErrors.messageFor(e, fallback = "Could not update your profile photo. Please try again.")
            } finally {
                _isPhotoBusy.value = false
            }
        }
    }

    /**
     * Surface an error when the picked profile photo can't be read from the
     * content resolver — e.g. a lapsed picker grant throwing SecurityException,
     * or a null input stream — so the "Add/Change photo" action doesn't appear
     * to silently do nothing. Mirrors NewPostScreen's read-failure handling.
     */
    fun onProfilePhotoReadFailed() {
        _photoErrorMessage.value = "Could not read the selected image. Please try again."
    }

    /** Removes the signed-in user's profile photo (issue #7), then reloads. */
    fun removeProfilePhoto(username: String) {
        if (_isPhotoBusy.value) return
        _isPhotoBusy.value = true
        _photoErrorMessage.value = null

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot remove profile photo")
                    _photoErrorMessage.value = "Not logged in."
                    return@launch
                }
                val token = userSession.sessionToken

                val response = api.removeProfilePhoto(token)
                if (response.isSuccessful) {
                    reloadProfileDetails(username, token)
                } else {
                    _photoErrorMessage.value = ApiErrors.messageFor(response, fallback = "Could not remove your profile photo. Please try again.")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error removing profile photo", e)
                _photoErrorMessage.value = ApiErrors.messageFor(e, fallback = "Could not remove your profile photo. Please try again.")
            } finally {
                _isPhotoBusy.value = false
            }
        }
    }

    /**
     * Reloads just the profile details (not the post grid), used after a
     * photo set/remove so the header avatar and owner-only status refresh
     * without disturbing pagination.
     */
    private suspend fun reloadProfileDetails(username: String, token: String) {
        val profileResponse = api.getProfileDetails(token, username)
        if (profileResponse.isSuccessful) {
            val profile = profileResponse.body()
            _profileDetails.value = profile
            _isFollowing.value = profile?.isFollowing ?: false
            _isBlocked.value = profile?.isBlocked ?: false
        } else {
            // The set/remove itself succeeded but this refresh didn't, so the
            // header would keep showing the old avatar/state. Surface it as a
            // photo error (a thrown network failure is already caught by the
            // calling set/remove) so the action doesn't look like it failed.
            _photoErrorMessage.value = ApiErrors.messageFor(
                profileResponse,
                fallback = "Your change was saved, but the profile couldn't refresh — pull to refresh."
            )
        }
    }

    fun toggleFollow(username: String) {
        val currentProfile = _profileDetails.value ?: return
        val isFollowing = currentProfile.isFollowing

        // Optimistic Update. Keep _isFollowing in sync with the profile so the
        // follow button and the follower count never drift apart.
        _profileDetails.value = currentProfile.copy(
            isFollowing = !isFollowing,
            followerCount = if (isFollowing) currentProfile.followerCount - 1 else currentProfile.followerCount + 1
        )
        _isFollowing.value = !isFollowing

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot toggle follow")
                    _errorMessage.value = "Not logged in."
                    return@launch
                }

                val response = if (isFollowing) {
                    api.unfollowUser(userSession.sessionToken, username)
                } else {
                    api.followUser(userSession.sessionToken, username)
                }

                if (!response.isSuccessful) {
                    // Revert on failure
                    _profileDetails.value = currentProfile
                    _isFollowing.value = isFollowing
                    _errorMessage.value = "Failed to update follow status"
                }
            } catch (e: Exception) {
                // Revert on error
                _profileDetails.value = currentProfile
                _isFollowing.value = isFollowing
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }

    fun toggleBlock(username: String) {
        val currentBlockedStatus = _isBlocked.value
        val currentProfile = _profileDetails.value

        // Optimistic Update
        _isBlocked.value = !currentBlockedStatus

        // Blocking also unfollows on the backend, so mirror that here. Only
        // decrement the follower count if we were actually following, otherwise
        // the count drifts (e.g. follow -> block -> follow would count twice).
        if (!currentBlockedStatus && currentProfile != null && currentProfile.isFollowing) {
            _profileDetails.value = currentProfile.copy(
                isFollowing = false,
                followerCount = currentProfile.followerCount - 1
            )
            _isFollowing.value = false
        }

        viewModelScope.launch {
            try {
                val userSession = keychainHelper.load(UserSession::class.java, service, account)
                if (userSession == null) {
                    Log.e(TAG, "No active session found — cannot toggle block")
                    _errorMessage.value = "Not logged in."
                    return@launch
                }

                val response = api.toggleBlock(userSession.sessionToken, username)

                if (!response.isSuccessful) {
                    // Revert on failure, including the optimistic unfollow side-effect.
                    _isBlocked.value = currentBlockedStatus
                    if (currentProfile != null) {
                        _profileDetails.value = currentProfile
                        _isFollowing.value = currentProfile.isFollowing
                    }
                    _errorMessage.value = "Failed to update block status"
                }
            } catch (e: Exception) {
                // Revert on error, including the optimistic unfollow side-effect.
                _isBlocked.value = currentBlockedStatus
                if (currentProfile != null) {
                    _profileDetails.value = currentProfile
                    _isFollowing.value = currentProfile.isFollowing
                }
                _errorMessage.value = ApiErrors.messageFor(e, fallback = "Something went wrong. Please try again.")
            }
        }
    }
}