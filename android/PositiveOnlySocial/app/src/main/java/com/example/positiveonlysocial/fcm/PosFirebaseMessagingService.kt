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
 *   notification whose tap carries the post id to MainActivity. In the
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

    /** Below API 33 POST_NOTIFICATIONS is auto-granted (normal permission); on
     * 33+ it's a runtime grant the user may have denied. */
    private fun canPostNotifications(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return true
        return ContextCompat.checkSelfPermission(
            this, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
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
