package com.example.positiveonlysocial.fcm

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Deep-link target for a tapped push notification (issues #342/#343/#444/#604)
 * and for a shared App Link (issues #382, #510).
 *
 * A tapped post notification, or a shared post link, parks the post id here; a
 * shared profile link or a new-follower notification parks the username; a
 * follow-request notification parks a request for the follow-request list. The
 * root NavGraph observes them and navigates, then clears them. Mirrors
 * ProfileTabNavigator (issue #347): a screen that isn't composed yet — the app is mid-launch from a cold
 * tap — can still hand off the request. Push is a nudge, never the source of
 * truth (#282), so a dropped request just leaves the user to find the outcome
 * in-app.
 */
object PushNavigator {
    private val _pendingPostId = MutableStateFlow<String?>(null)
    val pendingPostId: StateFlow<String?> = _pendingPostId

    private val _pendingProfileUsername = MutableStateFlow<String?>(null)
    val pendingProfileUsername: StateFlow<String?> = _pendingProfileUsername

    private val _pendingFollowRequests = MutableStateFlow(false)
    val pendingFollowRequests: StateFlow<Boolean> = _pendingFollowRequests

    fun openPost(postId: String) {
        _pendingPostId.value = postId
    }

    /** A shared profile link (issue #510) or a new-follower notification
     * (issue #604) asked us to open [username]'s profile. */
    fun openProfile(username: String) {
        _pendingProfileUsername.value = username
    }

    /** A follow-request notification (issue #604) asked us to open the
     * signed-in user's incoming follow requests. */
    fun openFollowRequests() {
        _pendingFollowRequests.value = true
    }

    fun clearRequest() {
        _pendingPostId.value = null
    }

    fun clearProfileRequest() {
        _pendingProfileUsername.value = null
    }

    fun clearFollowRequestsRequest() {
        _pendingFollowRequests.value = false
    }
}
