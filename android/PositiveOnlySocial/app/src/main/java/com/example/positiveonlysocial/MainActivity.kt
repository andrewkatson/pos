package com.example.positiveonlysocial

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import com.example.positiveonlysocial.di.DependencyProvider
import com.example.positiveonlysocial.fcm.PosFirebaseMessagingService
import com.example.positiveonlysocial.fcm.PushNavigator
import com.example.positiveonlysocial.ui.navigation.NavGraph
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme

class MainActivity : ComponentActivity() {

    // Android 13+ requires runtime consent to post notifications (issues
    // #342/#343). The result doesn't matter here — a denied permission just
    // means no banners; the token is still registered so nothing else breaks.
    private val requestNotificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        maybeRequestNotificationPermission()
        // The activity may have been launched by tapping a notification.
        handleNotificationIntent(intent)
        setContent {
            PositiveOnlySocialTheme {
                // A surface container using the 'background' color from the theme
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    NavGraph(
                        api = DependencyProvider.api,
                        keychainHelper = DependencyProvider.keychainHelper,
                        authManager = DependencyProvider.authManager
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        // A tap while the app was already running delivers the intent here.
        setIntent(intent)
        handleNotificationIntent(intent)
    }

    private fun maybeRequestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            requestNotificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    /** Route to the rejected post if this intent came from a notification tap.
     * FCM delivers the payload's data keys as string extras (issues #342/#343). */
    private fun handleNotificationIntent(intent: Intent?) {
        val postId = intent?.getStringExtra(PosFirebaseMessagingService.KEY_POST_IDENTIFIER)
        if (!postId.isNullOrEmpty()) {
            PushNavigator.openPost(postId)
        }
    }
}

@Preview(showBackground = true)
@Composable
fun MainActivityPreview() {
    PositiveOnlySocialTheme {
        NavGraph(
            api = PreviewHelpers.mockApi,
            keychainHelper = PreviewHelpers.mockKeychainHelper,
            authManager = PreviewHelpers.mockAuthManager
        )
    }
}