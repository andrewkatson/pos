package com.example.positiveonlysocial.data.auth

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.util.Log
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.credentials.exceptions.GetCredentialException
import androidx.credentials.exceptions.NoCredentialException
import com.example.positiveonlysocial.BuildConfig
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential

private const val TAG = "GoogleSignInProvider"

/**
 * What can go wrong on the way to a Google ID token (issue #10).
 *
 * [Cancelled] is deliberately separate: dismissing the account picker is a
 * choice, and the login screen shows nothing for it.
 */
sealed class GoogleSignInFailure(message: String) : Exception(message) {
    object NotConfigured : GoogleSignInFailure("Google sign-in is not set up in this build")
    object Cancelled : GoogleSignInFailure("Google sign-in was cancelled")
    object NoAccount : GoogleSignInFailure("No Google account is available on this device")
    /** No Activity to host the account picker — see [findActivity]. */
    object NoActivity : GoogleSignInFailure("Google sign-in can't be shown from here")
    class Failed(message: String) : GoogleSignInFailure(message)
}

/**
 * Walk the ContextWrapper chain looking for an Activity.
 *
 * Credential Manager renders the account picker over an Activity, and
 * `LocalContext.current` is only typed as a Context — under a preview, a test
 * harness, or any wrapping it may not be one. Finding it explicitly turns that
 * into a reportable failure instead of a ClassCastException from inside the
 * Google flow.
 */
internal fun Context.findActivity(): Activity? {
    var current: Context? = this
    while (current is ContextWrapper) {
        if (current is Activity) return current
        current = current.baseContext
    }
    return null
}

/**
 * Obtains a Google ID token to post to `login/google/`.
 *
 * An interface so the login screen never touches Credential Manager directly —
 * previews, unit tests and instrumentation runs inject a stub instead of trying
 * to drive a real account picker.
 */
interface GoogleSignInProviding {
    /** False when this build has no web OAuth client ID; the button is then hidden. */
    val isConfigured: Boolean

    /** Run the account picker and return the ID token Google issues. */
    suspend fun signIn(context: Context): String
}

/**
 * The real flow, via Credential Manager's Sign in with Google.
 *
 * Note which client ID this wants: Credential Manager takes the **web** OAuth
 * client ID, not the Android one, even though it runs on Android. Google mints
 * the ID token addressed to that web client, so it is the value the backend's
 * `GOOGLE_OAUTH_CLIENT_IDS` has to contain. (The Android client ID still has to
 * exist in the same Google Cloud project, keyed to the app's signing
 * certificate, or Google refuses to issue anything.)
 *
 * Supplied via `-PGOOGLE_WEB_CLIENT_ID` / gradle.properties like the FCM
 * identifiers, so an unconfigured build is simply one without a Google button —
 * and CI needs no Google credentials to stay green.
 */
class GoogleSignInProvider(
    private val webClientId: String = BuildConfig.GOOGLE_WEB_CLIENT_ID,
    private val credentialManagerFactory: (Context) -> CredentialManager = { CredentialManager.create(it) },
) : GoogleSignInProviding {

    override val isConfigured: Boolean
        get() = webClientId.isNotBlank()

    override suspend fun signIn(context: Context): String {
        if (!isConfigured) throw GoogleSignInFailure.NotConfigured

        // Resolved up front so "nothing to show the picker over" is a reported
        // failure rather than a crash inside Credential Manager.
        val activity = context.findActivity() ?: run {
            Log.w(TAG, "No Activity in the context chain; cannot show the Google account picker")
            throw GoogleSignInFailure.NoActivity
        }

        // GetSignInWithGoogleOption (rather than GetGoogleIdOption) shows the
        // full account picker every time. The filtered variant silently reuses
        // whichever account signed in last, which is wrong for a button the
        // user pressed to choose an account.
        val request = GetCredentialRequest.Builder()
            .addCredentialOption(GetSignInWithGoogleOption.Builder(webClientId).build())
            .build()

        val response = try {
            credentialManagerFactory(activity).getCredential(activity, request)
        } catch (e: GetCredentialCancellationException) {
            throw GoogleSignInFailure.Cancelled
        } catch (e: NoCredentialException) {
            throw GoogleSignInFailure.NoAccount
        } catch (e: GetCredentialException) {
            Log.w(TAG, "Credential Manager could not produce a Google credential", e)
            throw GoogleSignInFailure.Failed(e.message ?: "Google sign-in failed")
        }

        val credential = response.credential
        if (credential is CustomCredential &&
            credential.type == GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL
        ) {
            return GoogleIdTokenCredential.createFrom(credential.data).idToken
        }
        // Credential Manager can return a passkey or a saved password for other
        // request types; for this one anything else means something is wrong.
        Log.w(TAG, "Credential Manager returned an unexpected credential type: ${credential.type}")
        throw GoogleSignInFailure.Failed("Google returned an unexpected credential")
    }
}

/**
 * Stands in for Google where no account picker can be driven — Compose previews
 * and instrumentation runs. Mirrors StatefulStubbedAPI: it returns an unsigned
 * token carrying exactly the claims the stubbed API reads back out.
 */
class StubbedGoogleSignIn(
    private val email: String = "stubgoogleuser@example.com",
    private val sub: String = "stub-google-sub",
) : GoogleSignInProviding {

    override val isConfigured: Boolean = true

    override suspend fun signIn(context: Context): String {
        val encoder = java.util.Base64.getUrlEncoder().withoutPadding()
        val header = encoder.encodeToString("""{"alg":"none"}""".toByteArray())
        val claims = """{"sub":"$sub","email":"$email","email_verified":true}"""
        return "$header.${encoder.encodeToString(claims.toByteArray())}.stubsignature"
    }
}
