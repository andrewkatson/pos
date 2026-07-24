package com.example.positiveonlysocial.ui.navigation

import android.net.Uri

sealed class Screen(val route: String) {
    object Login : Screen("login")
    object Welcome : Screen("welcome")
    object Register : Screen("register")
    object CheckEmail : Screen("check_email/{email}?membershipNumber={membershipNumber}") {
        // Encoded because an email may contain reserved URI characters; the
        // navigation library decodes route arguments before handing them to
        // the destination. The membership number (issue #198) is an optional
        // query argument — present only right after registration.
        fun createRoute(email: String, membershipNumber: Int? = null): String {
            val base = "check_email/${Uri.encode(email)}"
            return if (membershipNumber != null) "$base?membershipNumber=$membershipNumber" else base
        }
    }
    object RequestReset : Screen("request_reset")
    object VerifyReset : Screen("verify_reset/{usernameOrEmail}") {
        fun createRoute(usernameOrEmail: String) = "verify_reset/$usernameOrEmail"
    }
    object ResetPassword : Screen("reset_password/{usernameOrEmail}") {
        fun createRoute(usernameOrEmail: String) = "reset_password/$usernameOrEmail"
    }
    object Home : Screen("home")
    object Feed : Screen("feed")
    object NewPost : Screen("new_post")
    object PostDetail : Screen("post_detail/{postId}") {
        fun createRoute(postId: String) = "post_detail/$postId"
    }
    object Profile : Screen("profile/{username}") {
        fun createRoute(username: String) = "profile/$username"
    }
    object Settings : Screen("settings")
    object Appeals : Screen("appeals")
    object BlockedUsers : Screen("blocked_users")
}
