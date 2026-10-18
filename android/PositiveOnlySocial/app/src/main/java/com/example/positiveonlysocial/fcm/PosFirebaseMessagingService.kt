package com.example.positiveonlysocial.fcm

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.example.positiveonlysocial.MainActivity
import com.example.positiveonlysocial.R
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

/**
 * Receives FCM push (issues #342/#343).
 *
 * - onNewToken: the token rotated (or was first issued); re-register it.
 * - onMessageReceived: fires while the app is foregrounded — build a
 *   notification whose tap carries the post id to MainActivity. Rejections
 *   and social activity (new posts, comments, likes — #444) get separate
 *   channels so the user can mute one in system settings without the other. In the
 *   background the system displays the message's notification block itself and
 *   delivers the data payload as launch-intent extras, which MainActivity reads.
 */
class PosFirebaseMessagingService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        PushRegistrar.uploadToken(token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        // On Android 13+ posting a notification without POST_NOTIFICATIONS just
        // no-ops (the user can deny it — see MainActivity), so skip the work and
        // never risk a SecurityException on a denied permission.
        if (!canPostNotifications()) return

        val postId = message.data[KEY_POST_IDENTIFIER]
        val type = message.data[KEY_TYPE]
        val isActivity = type in ACTIVITY_TYPES
        // A rejection keeps its single slot; each piece of activity gets its own
        // so a like doesn't replace a comment, while a second like on the same
        // post replaces the first rather than stacking.
        val notificationId = if (isActivity) "$type:$postId".hashCode() else NOTIFICATION_ID
        val title = message.notification?.title ?: "Good Vibes Only"
        val body = message.notification?.body ?: ""

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            // Android routes by post_identifier only (the web deep_link isn't
            // used here), matching the extras FCM places on a background tap.
            // `type` rides along so the tap handler can gate on it, the way iOS
            // does — a future push type carrying post_identifier for another
            // reason must not deep-link to a post.
            if (postId != null) putExtra(KEY_POST_IDENTIFIER, postId)
            type?.let { putExtra(KEY_TYPE, it) }
        }
        // Request code per notification: with a shared one, FLAG_UPDATE_CURRENT
        // would rewrite every earlier notification's extras to this post.
        val pendingIntent = PendingIntent.getActivity(
            this, notificationId, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

        val channelId = if (isActivity) ACTIVITY_CHANNEL_ID else CHANNEL_ID
        ensureChannels()
        val notification = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .build()

        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(notificationId, notification)
    }

    /** Below API 33 POST_NOTIFICATIONS is auto-granted (normal permission); on
     * 33+ it's a runtime grant the user may have denied. */
    private fun canPostNotifications(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return true
        return ContextCompat.checkSelfPermission(
            this, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
    }

    private fun ensureChannels() {
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        // minSdk is 26, so the channel API is always available.
        manager.createNotificationChannel(NotificationChannel(
            CHANNEL_ID, "Post moderation", NotificationManager.IMPORTANCE_DEFAULT))
        manager.createNotificationChannel(NotificationChannel(
            ACTIVITY_CHANNEL_ID, "Activity", NotificationManager.IMPORTANCE_DEFAULT))
    }

    companion object {
        // Data keys from the backend payload (user_system/push.build_rejection_payload).
        // Android routes by post_identifier; the web-only deep_link is ignored here.
        const val KEY_POST_IDENTIFIER = "post_identifier"
        const val KEY_TYPE = "type"
        // Push types that deep-link to a post (backend PUSH_TYPE_* kinds); the
        // tap handler gates on these so a future type can't misroute.
        const val TYPE_POST_REJECTED = "post_rejected"
        val ACTIVITY_TYPES = setOf("new_post", "new_comment", "new_like")
        val POST_TYPES = ACTIVITY_TYPES + TYPE_POST_REJECTED
        private const val CHANNEL_ID = "post_moderation"
        private const val ACTIVITY_CHANNEL_ID = "activity"
        private const val NOTIFICATION_ID = 342
    }
}
