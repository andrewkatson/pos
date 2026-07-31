package com.example.positiveonlysocial.fcm

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import androidx.core.app.NotificationCompat
import com.example.positiveonlysocial.MainActivity
import com.example.positiveonlysocial.R
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

/**
 * Receives FCM push (issues #342/#343).
 *
 * - onNewToken: the token rotated (or was first issued); re-register it.
 * - onMessageReceived: fires while the app is foregrounded — build a
 *   notification whose tap carries the post id to MainActivity. In the
 *   background the system displays the message's notification block itself and
 *   delivers the data payload as launch-intent extras, which MainActivity reads.
 */
class PosFirebaseMessagingService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        PushRegistrar.uploadToken(token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val postId = message.data[KEY_POST_IDENTIFIER]
        val title = message.notification?.title ?: "Good Vibes Only"
        val body = message.notification?.body ?: ""

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            // Mirror the data keys FCM would place as extras on a background tap,
            // so MainActivity's handling is identical either way.
            if (postId != null) putExtra(KEY_POST_IDENTIFIER, postId)
            message.data[KEY_DEEP_LINK]?.let { putExtra(KEY_DEEP_LINK, it) }
        }
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

        ensureChannel()
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .build()

        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID, notification)
    }

    private fun ensureChannel() {
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        // minSdk is 26, so the channel API is always available.
        val channel = NotificationChannel(
            CHANNEL_ID, "Post moderation", NotificationManager.IMPORTANCE_DEFAULT)
        manager.createNotificationChannel(channel)
    }

    companion object {
        // Data keys from the backend payload (user_system/push.build_rejection_payload).
        const val KEY_POST_IDENTIFIER = "post_identifier"
        const val KEY_DEEP_LINK = "deep_link"
        private const val CHANNEL_ID = "post_moderation"
        private const val NOTIFICATION_ID = 342
    }
}
