package com.example.positiveonlysocial.util

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.util.Log
import android.widget.Toast

/**
 * Builds the website links shared from a post's or comment's options menu, and
 * launches the Android system share sheet with one (issue #34, Scope A).
 *
 * These links point at the website (they currently require login to view —
 * public viewing / App Links deep-linking straight into the app is the tracked
 * Scope B follow-up). The URL builders are kept pure so they can be unit-tested
 * without an Android runtime; only [shareText] touches the framework.
 */
object ShareLinks {
    /** The website origin every shared link is rooted at. */
    const val WEB_BASE_URL = "https://smiling.social"

    /** The website URL for the post with [postIdentifier]. */
    fun postUrl(postIdentifier: String): String =
        "$WEB_BASE_URL/post/$postIdentifier"

    /**
     * The website URL for a single comment: the post URL plus a
     * `#comment-<id>` fragment so the page can scroll to it.
     */
    fun commentUrl(postIdentifier: String, commentIdentifier: String): String =
        "${postUrl(postIdentifier)}#comment-$commentIdentifier"

    /**
     * Launch the system share sheet (chooser) with [text] as plain-text content,
     * e.g. one of the URLs above. Kept out of the URL builders above so those
     * stay unit-testable.
     */
    fun shareText(context: Context, text: String) {
        val sendIntent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, text)
        }
        // FLAG_ACTIVITY_NEW_TASK is required when the caller's Context isn't an
        // Activity (a Compose LocalContext can be a plain ContextWrapper), or
        // startActivity throws AndroidRuntimeException.
        val chooser = Intent.createChooser(sendIntent, null).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        try {
            context.startActivity(chooser)
        } catch (e: ActivityNotFoundException) {
            // No app can handle the share (rare, but possible on stripped-down
            // devices). Fail softly rather than crash.
            Log.w("ShareLinks", "No activity to handle share intent", e)
            Toast.makeText(context, "No app available to share.", Toast.LENGTH_SHORT).show()
        }
    }
}
