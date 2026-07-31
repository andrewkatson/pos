package com.example.positiveonlysocial.fcm

import com.example.positiveonlysocial.BuildConfig
import com.google.firebase.FirebaseOptions

/**
 * FCM-for-Android configuration (issues #342/#343), read from BuildConfig fields
 * that are populated from the (public) Firebase project identifiers passed at
 * build time — see app/build.gradle.kts. When any value is empty push is not
 * configured: no FirebaseApp is initialized and every push path is a no-op, so
 * the app builds and runs without a google-services.json (and without the
 * google-services Gradle plugin). Push is a nudge, never the source of truth
 * (#282 in-app reconciliation is), so silently doing nothing is correct.
 */
object FcmConfig {

    val isConfigured: Boolean
        get() = BuildConfig.FCM_PROJECT_ID.isNotEmpty() &&
            BuildConfig.FCM_APPLICATION_ID.isNotEmpty() &&
            BuildConfig.FCM_API_KEY.isNotEmpty() &&
            BuildConfig.FCM_SENDER_ID.isNotEmpty()

    /** The options we'd otherwise get from google-services.json, built by hand. */
    fun firebaseOptions(): FirebaseOptions =
        FirebaseOptions.Builder()
            .setProjectId(BuildConfig.FCM_PROJECT_ID)
            .setApplicationId(BuildConfig.FCM_APPLICATION_ID)
            .setApiKey(BuildConfig.FCM_API_KEY)
            .setGcmSenderId(BuildConfig.FCM_SENDER_ID)
            .build()
}
