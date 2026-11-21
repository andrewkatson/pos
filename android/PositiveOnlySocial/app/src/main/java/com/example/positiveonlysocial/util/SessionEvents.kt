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

    /** Announce that the signed-in account is now called [username]; the name
     * it gave up stays reserved for it until [formerHeldUntilMillis] (epoch ms,
     * null if unknown). */
    fun usernameChanged(username: String, formerHeldUntilMillis: Long? = null) {
        _usernameChanges.tryEmit(UsernameChange(username, formerHeldUntilMillis))
    }
}

/** A rename: the new name, and until when the given-up name stays held for
 * the account (epoch ms) — after that someone else may hold it. */
data class UsernameChange(val username: String, val formerHeldUntilMillis: Long?)
