package com.example.positiveonlysocial.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
            RegisterScreen(navController, api, keychainHelper, authManager)
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
            // On first composition: if the token is gone (process death / direct deep-link),
            // redirect to Login so the user restarts the flow rather than seeing a blank screen.
            // Keyed on Unit so it fires exactly once — avoiding the key-change race of
            // LaunchedEffect(pendingResetToken) where the empty initial value could redirect
            // before the onVerified write propagated.
            LaunchedEffect(Unit) {
                if (pendingResetToken.isEmpty()) {
                    navController.navigate(Screen.Login.route) {
                        popUpTo(Screen.RequestReset.route) { inclusive = true }
                    }
                }
            }
            if (pendingResetToken.isNotEmpty()) {
                ResetPasswordScreen(navController, api, keychainHelper, usernameOrEmail, pendingResetToken)
            }
        }

        // Main App Flow
        composable(Screen.Home.route) {
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
    }
}
