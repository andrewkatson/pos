package com.example.positiveonlysocial.fcm

import android.content.Context
import android.util.Log
import com.example.positiveonlysocial.data.model.RegisterDeviceRequest
import com.example.positiveonlysocial.data.model.UserSession
import com.example.positiveonlysocial.di.DependencyProvider
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * Owns FCM initialization and token upload (issues #342/#343). Best-effort
 * throughout: when push isn't configured, or there's no session, or the upload
 * fails, it simply does nothing and the user relies on in-app reconciliation
 * (#282). Nothing here ever throws to its caller.
 */
object PushRegistrar {
    private const val TAG = "PushRegistrar"
    // The Keychain coordinates the app stores the session under, matching the
    // ViewModels (e.g. ProfileViewModel).
    private const val SERVICE = "positive-only-social.Positive-Only-Social"
    private const val ACCOUNT = "userSessionToken"
    private const val PLATFORM = "android"

    /** Initialize a FirebaseApp from BuildConfig when configured. Called once at
     * app startup; a no-op (and safe to call) when push isn't configured. */
    fun initialize(context: Context) {
        if (!FcmConfig.isConfigured) return
        if (FirebaseApp.getApps(context).isEmpty()) {
            try {
                FirebaseApp.initializeApp(context, FcmConfig.firebaseOptions())
            } catch (e: Exception) {
                Log.w(TAG, "FirebaseApp init failed; push disabled", e)
            }
        }
    }

    /** Fetch the current FCM token and upload it. Safe to call whenever the app
     * reaches a signed-in state; a no-op when unconfigured. */
    fun registerCurrentToken() {
        if (!FcmConfig.isConfigured) return
        try {
            FirebaseMessaging.getInstance().token
                .addOnSuccessListener { token -> uploadToken(token) }
                // The token fetch is async: a failure resolves the Task, it
                // doesn't throw here, so surface it via the failure listener.
                .addOnFailureListener { e -> Log.w(TAG, "Fetching FCM token failed", e) }
        } catch (e: Exception) {
            Log.w(TAG, "Fetching FCM token failed", e)
        }
    }

    /** Upload a token to the backend for the current session (rotation calls
     * this from onNewToken). No session → nothing to register. */
    fun uploadToken(token: String) {
        val session = try {
            DependencyProvider.keychainHelper.load(UserSession::class.java, SERVICE, ACCOUNT)
        } catch (e: Exception) {
            null
        } ?: return

        CoroutineScope(Dispatchers.IO).launch {
            try {
                DependencyProvider.api.registerDevice(
                    session.sessionToken, RegisterDeviceRequest(platform = PLATFORM, token = token))
            } catch (e: Exception) {
                // Best-effort: push is never the source of truth (#282).
                Log.w(TAG, "Device token upload failed", e)
            }
        }
    }
}
