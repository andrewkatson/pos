package com.example.positiveonlysocial.util

import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * A tiny app-wide event bus for post lifecycle changes that need to cross screen
 * (and ViewModel) boundaries — the Android analogue of the iOS `.postDeleted`
 * NotificationCenter notification.
 *
 * The feeds and the profile grids live in different nav back-stack entries than
 * the post detail screen, so a delete performed on one of them can't otherwise
 * reach the others' cached lists. Without this, the deleted post's now-missing
 * image lingers as an empty black tile until the user logs out. See issue #256.
 *
 * Every list picks these up through
 * [com.example.positiveonlysocial.models.viewmodels.PostListActions], which also
 * publishes here when a post is deleted from a list (issue #267).
 */
object PostEvents {
    // extraBufferCapacity lets tryEmit succeed without a collector suspending the
    // emitter; deletes are rare so a small buffer is plenty. DROP_OLDEST keeps
    // tryEmit non-suspending and never failing even if the buffer fills while the
    // collector is briefly busy, so a delete event is never silently dropped.
    private val _deletedPostIds = MutableSharedFlow<String>(
        extraBufferCapacity = 16,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )
    val deletedPostIds: SharedFlow<String> = _deletedPostIds.asSharedFlow()

    /** Announce that the post with [postIdentifier] was deleted. */
    fun postDeleted(postIdentifier: String) {
        _deletedPostIds.tryEmit(postIdentifier)
    }

    // Commenting turned off/on (issue #492): the detail screen's toggle has to
    // reach the list rows too, or their menu keeps offering the stale action.
    private val _commentsDisabledChanges = MutableSharedFlow<Pair<String, Boolean>>(
        extraBufferCapacity = 16,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )
    val commentsDisabledChanges: SharedFlow<Pair<String, Boolean>> = _commentsDisabledChanges.asSharedFlow()

    /** Announce that commenting on [postIdentifier] was turned off or on. */
    fun commentsDisabledChanged(postIdentifier: String, commentsDisabled: Boolean) {
        _commentsDisabledChanges.tryEmit(postIdentifier to commentsDisabled)
    }
}
