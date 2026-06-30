package com.example.positiveonlysocial.util

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * A tiny app-wide event bus for post lifecycle changes that need to cross screen
 * (and ViewModel) boundaries — the Android analogue of the iOS `.postDeleted`
 * NotificationCenter notification.
 *
 * The Home grid's [com.example.positiveonlysocial.models.viewmodels.HomeViewModel]
 * lives in a different nav back-stack entry than the post detail screen, so a
 * delete performed in the detail screen can't otherwise reach the grid's cached
 * list. Without this, the deleted post's now-missing image lingers as an empty
 * black tile until the user logs out. See issue #256.
 */
object PostEvents {
    // extraBufferCapacity lets tryEmit succeed without a collector suspending the
    // emitter; deletes are rare so a small buffer is plenty.
    private val _deletedPostIds = MutableSharedFlow<String>(extraBufferCapacity = 16)
    val deletedPostIds: SharedFlow<String> = _deletedPostIds.asSharedFlow()

    /** Announce that the post with [postIdentifier] was deleted. */
    fun postDeleted(postIdentifier: String) {
        _deletedPostIds.tryEmit(postIdentifier)
    }
}
