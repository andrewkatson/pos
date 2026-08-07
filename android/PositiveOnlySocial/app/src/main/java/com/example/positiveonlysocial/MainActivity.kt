package com.example.positiveonlysocial

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import com.example.positiveonlysocial.di.DependencyProvider
import com.example.positiveonlysocial.fcm.FcmConfig
import com.example.positiveonlysocial.fcm.PosFirebaseMessagingService
import com.example.positiveonlysocial.fcm.PushNavigator
import com.example.positiveonlysocial.ui.navigation.NavGraph
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme
import com.example.positiveonlysocial.util.ShareLinks

class MainActivity : ComponentActivity() {

    // Android 13+ requires runtime consent to post notifications (issues
    // #342/#343). The result doesn't matter here — a denied permission just
    // means no banners; the token is still registered so nothing else breaks.
    private val requestNotificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        maybeRequestNotificationPermission()
        // The activity may have been launched by tapping a notification, or by
        // opening a shared post link (issue #382).
        handleNotificationIntent(intent)
        handleSharedLinkIntent(intent)
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
        handleSharedLinkIntent(intent)
    }

    private fun maybeRequestNotificationPermission() {
        // Don't prompt for a permission the app can't use yet: when push isn't
        // configured every push path is a no-op, so asking would be pointless
        // (and contrary to the graceful-degradation rule).
        if (!FcmConfig.isConfigured) return
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        // Only ask when we don't already hold it — no point re-launching the
        // request on every cold start once the user has granted it. (The system
        // itself suppresses the dialog after the user has denied twice.)
        val granted = ContextCompat.checkSelfPermission(
            this, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        if (!granted) {
            requestNotificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    /** Route to the rejected post if this intent came from a notification tap.
     * FCM delivers the payload's data keys as string extras (issues #342/#343). */
    private fun handleNotificationIntent(intent: Intent?) {
        val postId = intent?.getStringExtra(PosFirebaseMessagingService.KEY_POST_IDENTIFIER)
        val type = intent?.getStringExtra(PosFirebaseMessagingService.KEY_TYPE)
        // Gate on the payload's type (like iOS) so a future push kind that also
        // carries post_identifier can't misroute to a post.
        if (!postId.isNullOrEmpty() && type == PosFirebaseMessagingService.TYPE_POST_REJECTED) {
            PushNavigator.openPost(postId)
            // Consume them so an Activity recreation (rotation / process death)
            // doesn't re-read the same extras and navigate again.
            intent.removeExtra(PosFirebaseMessagingService.KEY_POST_IDENTIFIER)
            intent.removeExtra(PosFirebaseMessagingService.KEY_TYPE)
        }
    }

    /** Route to the post a shared App Link points at (issue #382).
     *
     * Deliberately goes through [PushNavigator] rather than letting NavHost
     * handle the deep link itself: PostDetail is an authenticated screen, and
     * NavHost would build a back stack straight to it even when the user is
     * signed out. The navigator parks the request until the graph reports a
     * session, which is the same path a tapped push notification takes. */
    private fun handleSharedLinkIntent(intent: Intent?) {
        if (intent == null || intent.action != Intent.ACTION_VIEW) return
        val link = ShareLinks.parseSharedPostLink(intent.dataString) ?: return
        PushNavigator.openPost(link.postIdentifier)
        // Consume the data so an Activity recreation (rotation / process death)
        // doesn't re-read the same link and navigate again, matching how the
        // notification extras above are cleared.
        intent.data = null
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