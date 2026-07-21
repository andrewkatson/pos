package com.example.positiveonlysocial.ui.navigation

import androidx.navigation.NavController
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * A one-shot request to show the signed-in user's own profile, which lives on the
 * first bottom-nav destination rather than on the root stack (issue #347).
 *
 * The bottom navigation controller is private to
 * [com.example.positiveonlysocial.ui.main.MainScreen], and the screens that link
 * to a profile (the feed rows, the post detail screen, the search results) only
 * ever hold the *root* controller — and the post detail screen isn't even
 * composed at the same time as the bottom bar. So the request is parked here and
 * MainScreen consumes it, the same way [
 * com.example.positiveonlysocial.data.auth.AuthenticationManager.forcedLogout] is
 * consumed by the root nav graph.
 */
object ProfileTabNavigator {

    private val _openOwnProfileRequested = MutableStateFlow(false)
    val openOwnProfileRequested: StateFlow<Boolean> = _openOwnProfileRequested.asStateFlow()

    /** Ask for the Profile bottom-nav destination to be selected. */
    fun requestOwnProfile() {
        _openOwnProfileRequested.value = true
    }

    /** Called by MainScreen once it has selected the tab. */
    fun clearRequest() {
        _openOwnProfileRequested.value = false
    }
}

/**
 * Opens [username]'s profile from a screen that holds the *root* nav controller.
 *
 * Anyone else's profile is pushed onto the root stack as before. Your own is the
 * Profile bottom-nav destination (issue #347), so tapping your own name selects
 * that tab instead of pushing a second, back-arrowed copy of your profile — which
 * would leave two different ways to view the same thing.
 */
fun NavController.openProfileFor(username: String, currentUsername: String?) {
    if (currentUsername == null || username != currentUsername) {
        navigate(Screen.Profile.createRoute(username))
        return
    }

    ProfileTabNavigator.requestOwnProfile()

    // Already inside the bottom-nav host (e.g. tapping your own name in the
    // feed): nothing to pop, MainScreen just switches tabs. Otherwise come back
    // down to it first.
    if (currentBackStackEntry?.destination?.route != Screen.Home.route &&
        !popBackStack(Screen.Home.route, /* inclusive = */ false)
    ) {
        navigate(Screen.Home.route)
    }
}
