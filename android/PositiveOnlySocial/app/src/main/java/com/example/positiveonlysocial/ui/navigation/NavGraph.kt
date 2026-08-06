package com.example.positiveonlysocial.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.fcm.PushNavigator
import com.example.positiveonlysocial.fcm.PushRegistrar
import com.example.positiveonlysocial.models.viewmodels.FollowListMode
import com.example.positiveonlysocial.ui.auth.*
import com.example.positiveonlysocial.ui.main.*

@Composable
fun NavGraph(
    navController: NavHostController = rememberNavController(),
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    authManager: AuthenticationManager
) {
    // Holds the reset token in memory between VerifyReset and ResetPassword screens.
    // Not passed via the nav route to avoid logging/persisting a bearer credential.
    var pendingResetToken by remember { mutableStateOf("") }

    // When the backend revokes the session (e.g. the account was banned),
    // send the user back to the welcome screen from wherever they are.
    val forcedLogout by authManager.forcedLogout.collectAsState()
    LaunchedEffect(forcedLogout) {
        if (forcedLogout) {
            authManager.clearForcedLogout()
            navController.navigate(Screen.Welcome.route) {
                // Welcome is the start destination, so popping to it
                // inclusively clears every authenticated screen.
                popUpTo(Screen.Welcome.route) { inclusive = true }
                launchSingleTop = true
            }
        }
    }

    // Something asked us to open a post: a tapped "post rejected" notification
    // (issues #342/#343), or a shared https://smiling.social/post/<id> App Link
    // parsed in MainActivity (issue #382). Only route into the authenticated
    // PostDetail once logged in: a stale request while logged out is left
    // pending (not cleared) and consumed after login — keying the effect on
    // isLoggedIn re-runs it when auth flips — instead of pushing an
    // authenticated screen from the Welcome flow.
    //
    // This is also why PostDetail carries no navDeepLink: NavHost would resolve
    // the incoming VIEW intent itself and build a back stack straight to an
    // authenticated screen, with no session behind it.
    val pendingPostId by PushNavigator.pendingPostId.collectAsState()
    val pushIsLoggedIn by authManager.isLoggedIn.collectAsState()
    LaunchedEffect(pendingPostId, pushIsLoggedIn) {
        val postId = pendingPostId ?: return@LaunchedEffect
        if (!pushIsLoggedIn) return@LaunchedEffect
        PushNavigator.clearRequest()
        navController.navigate(Screen.PostDetail.createRoute(postId)) {
            launchSingleTop = true
        }
    }

    NavHost(
        navController = navController,
        startDestination = Screen.Welcome.route
    ) {
        // Auth Flow
        composable(Screen.Welcome.route) {
            WelcomeScreen(navController, api, keychainHelper, authManager)
        }
        composable(Screen.Login.route) {
            LoginScreen(navController, api, keychainHelper, authManager)
        }
        composable(Screen.Register.route) {
            RegisterScreen(navController, api)
        }
        composable(
            route = Screen.CheckEmail.route,
            arguments = listOf(
                navArgument("email") { type = NavType.StringType },
                navArgument("membershipNumber") {
                    type = NavType.StringType
                    nullable = true
                    defaultValue = null
                }
            )
        ) { backStackEntry ->
            // The route arg is Uri-encoded by Screen.CheckEmail.createRoute and
            // decoded by the navigation library when it parses the route, so
            // this is already the plain address.
            val email = backStackEntry.arguments?.getString("email") ?: ""
            // Present only right after registration (issue #198); used to greet
            // the new member.
            val membershipNumber = backStackEntry.arguments?.getString("membershipNumber")?.toIntOrNull()
            CheckEmailScreen(navController, api, email, membershipNumber)
        }
        composable(Screen.RequestReset.route) {
            RequestResetScreen(navController, api, keychainHelper)
        }
        composable(
            route = Screen.VerifyReset.route,
            arguments = listOf(navArgument("usernameOrEmail") { type = NavType.StringType })
        ) { backStackEntry ->
            val usernameOrEmail = backStackEntry.arguments?.getString("usernameOrEmail") ?: ""
            VerifyResetScreen(navController, api, keychainHelper, usernameOrEmail,
                onVerified = { token -> pendingResetToken = token })
        }
        composable(
            route = Screen.ResetPassword.route,
            arguments = listOf(navArgument("usernameOrEmail") { type = NavType.StringType })
        ) { backStackEntry ->
            val usernameOrEmail = backStackEntry.arguments?.getString("usernameOrEmail") ?: ""
            // Check at composition time (not in a coroutine) so the branch is decided
            // synchronously — no race between the LaunchedEffect clock and the state write
            // from onVerified().  Process death / direct deep-link: token is "" → schedule
            // the redirect and render nothing.  Normal flow: token is set → render screen.
            if (pendingResetToken.isEmpty()) {
                LaunchedEffect(Unit) {
                    navController.navigate(Screen.Login.route) {
                        popUpTo(Screen.RequestReset.route) { inclusive = true }
                    }
                }
            } else {
                ResetPasswordScreen(navController, api, keychainHelper, usernameOrEmail, pendingResetToken)
            }
        }

        // Main App Flow
        composable(Screen.Home.route) {
            // Reaching Home means the user is signed in, so this reliably covers
            // the just-logged-in case for push registration (issues #342/#343).
            LaunchedEffect(Unit) { PushRegistrar.registerCurrentToken() }
            MainScreen(navController, api, keychainHelper, authManager)
        }
        
        // These are reachable from MainScreen or other screens, but MainScreen handles its own bottom nav.
        // However, Profile and PostDetail are usually pushed onto the root stack (covering bottom nav).
        // So we define them here.
        
        composable(
            route = Screen.Profile.route,
            arguments = listOf(navArgument("username") { type = NavType.StringType })
        ) { backStackEntry ->
            val username = backStackEntry.arguments?.getString("username") ?: ""
            ProfileScreen(navController, api, keychainHelper, username)
        }
        
        composable(
            route = Screen.PostDetail.route,
            arguments = listOf(navArgument("postId") { type = NavType.StringType })
        ) { backStackEntry ->
            val postId = backStackEntry.arguments?.getString("postId") ?: ""
            PostDetailScreen(navController, api, keychainHelper, postId)
        }

        composable(
            route = Screen.TagFeed.route,
            arguments = listOf(navArgument("tag") { type = NavType.StringType })
        ) { backStackEntry ->
            // Uri-encoded by Screen.TagFeed.createRoute and decoded by the
            // navigation library, so this is already the plain tag (issue #379).
            val tag = backStackEntry.arguments?.getString("tag") ?: ""
            TagFeedScreen(navController, api, keychainHelper, tag)
        }

        composable(Screen.Appeals.route) {
            AppealsScreen(navController, api, keychainHelper)
        }

        composable(Screen.BlockedUsers.route) {
            BlockedUsersScreen(navController, api, keychainHelper)
        }

        // Your own followers / following — only your own, since the endpoints
        // take no username (issue #8). The mode arg picks which list.
        composable(
            route = Screen.FollowList.route,
            arguments = listOf(navArgument("mode") { type = NavType.StringType })
        ) { backStackEntry ->
            val mode = FollowListMode.fromRoute(backStackEntry.arguments?.getString("mode"))
            FollowListScreen(navController, api, keychainHelper, mode)
        }
    }
}
