package com.example.positiveonlysocial.fcm

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Deep-link target for a tapped push notification (issues #342/#343).
 *
 * A tapped "post rejected" notification parks the post id here; the root
 * NavGraph observes it and navigates to the post, then clears it. Mirrors
 * ProfileTabNavigator (issue #347): a screen that isn't composed yet — the app
 * is mid-launch from a cold notification tap — can still hand off the request.
 * Push is a nudge, never the source of truth (#282), so a dropped request just
 * leaves the user to find the outcome in-app.
 */
object PushNavigator {
    private val _pendingPostId = MutableStateFlow<String?>(null)
    val pendingPostId: StateFlow<String?> = _pendingPostId

    fun openPost(postId: String) {
        _pendingPostId.value = postId
    }

    fun clearRequest() {
        _pendingPostId.value = null
    }
}
