package com.example.positiveonlysocial.fcm

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Deep-link target for a tapped push notification (issues #342/#343) and for a
 * shared App Link (issues #382, #510).
 *
 * A tapped "post rejected" notification, or a shared post link, parks the post
 * id here; a shared profile link parks the username. The root NavGraph observes
 * both and navigates, then clears them. Mirrors ProfileTabNavigator (issue
 * #347): a screen that isn't composed yet — the app is mid-launch from a cold
 * tap — can still hand off the request. Push is a nudge, never the source of
 * truth (#282), so a dropped request just leaves the user to find the outcome
 * in-app.
 */
object PushNavigator {
    private val _pendingPostId = MutableStateFlow<String?>(null)
    val pendingPostId: StateFlow<String?> = _pendingPostId

    private val _pendingProfileUsername = MutableStateFlow<String?>(null)
    val pendingProfileUsername: StateFlow<String?> = _pendingProfileUsername

    fun openPost(postId: String) {
        _pendingPostId.value = postId
    }

    /** A shared profile link (issue #510) asked us to open [username]'s profile. */
    fun openProfile(username: String) {
        _pendingProfileUsername.value = username
    }

    fun clearRequest() {
        _pendingPostId.value = null
    }

    fun clearProfileRequest() {
        _pendingProfileUsername.value = null
    }
}
