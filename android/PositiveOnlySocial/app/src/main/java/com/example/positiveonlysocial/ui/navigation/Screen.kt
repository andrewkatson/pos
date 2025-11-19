package com.example.positiveonlysocial.ui.navigation

sealed class Screen(val route: String) {
    object Login : Screen("login")
    object Register : Screen("register")
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
}
