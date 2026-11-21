package com.example.positiveonlysocial.util

import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * App-wide events about the signed-in session, alongside [PostEvents].
 *
 * View models kept alive in other back-stack entries (the Profile tab's
 * [com.example.positiveonlysocial.models.viewmodels.HomeViewModel], every list's
 * [com.example.positiveonlysocial.models.viewmodels.PostListActions]) cache the
 * signed-in username to tell your own posts from others'. A rename from
 * Settings (issue #594) reaches them here.
 */
object SessionEvents {
    private val _usernameChanges = MutableSharedFlow<UsernameChange>(
        extraBufferCapacity = 4,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )
    val usernameChanges: SharedFlow<UsernameChange> = _usernameChanges.asSharedFlow()

    /** Announce that the signed-in account is now called [username], and which
     * old name the server says is still reserved for it ([formerUsername]) until
     * when ([formerHeldUntilMillis], epoch ms) — null when none is. */
    fun usernameChanged(username: String, formerUsername: String? = null, formerHeldUntilMillis: Long? = null) {
        _usernameChanges.tryEmit(UsernameChange(username, formerUsername, formerHeldUntilMillis))
    }
}

/** A rename: the new name, and the server-confirmed old name still held for
 * the account with when its hold ends (epoch ms) — after that, or for any other
 * old name, someone else may hold it. */
data class UsernameChange(val username: String, val formerUsername: String?, val formerHeldUntilMillis: Long?)
