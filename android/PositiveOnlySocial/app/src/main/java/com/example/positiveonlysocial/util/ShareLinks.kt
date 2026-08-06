package com.example.positiveonlysocial.util

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.util.Log
import android.widget.Toast
import java.net.URI

/**
 * A shared link that resolved to a post, and optionally to one comment on it
 * (issue #382).
 */
data class SharedPostLink(
    val postIdentifier: String,
    /**
     * The comment a `#comment-<id>` fragment named, or null for a plain post
     * link. Carried so a shared comment link routes to its post rather than
     * being rejected outright; the app opens the post detail either way.
     */
    val commentIdentifier: String?
)

/**
 * Both ends of a shared post link: the website URLs built from a post's or
 * comment's options menu (issue #34), and the parse of the same URL when
 * Android hands it back as an App Link (issue #382).
 *
 * The website renders these links for signed-out recipients too (issue #381),
 * so a link is useful whether or not the app is installed — which is what makes
 * claiming the `https://smiling.social/post/` path prefix with `autoVerify`
 * safe: a device without the app just opens the web page.
 *
 * (Spelling that prefix with a trailing wildcard would end this comment early:
 * Kotlin block comments nest, so the `/` + `*` would open one.)
 *
 * Everything except [shareText] is pure (no Android framework, [URI] rather
 * than `android.net.Uri`) so it unit-tests on the JVM without a runtime.
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
     * The website hosts this app claims as App Links. Both are declared in the
     * manifest's `autoVerify` intent-filter and both serve the same site, so a
     * link shared with the `www.` prefix opens the app too.
     */
    val LINK_HOSTS = setOf("smiling.social", "www.smiling.social")

    private const val COMMENT_FRAGMENT_PREFIX = "comment-"

    /**
     * The inverse of the builders above: what an App Link Android launched us
     * with refers to, or null when [url] is not one of ours (issue #382).
     *
     * Deliberately strict. A VIEW intent can be sent by any app, not only by
     * the verified-link path, so scheme, host and path shape are all checked
     * before the identifier is used to navigate — a URL that merely looks
     * similar must not send the user somewhere unexpected. A trailing slash is
     * tolerated because chat apps and link shorteners add one freely, and an
     * unrecognized fragment is ignored rather than failing the whole link: the
     * post is still the right destination.
     */
    fun parseSharedPostLink(url: String?): SharedPostLink? {
        if (url.isNullOrBlank()) return null
        val uri = try {
            URI(url)
        } catch (e: Exception) {
            // A malformed URL is simply not one of ours.
            Log.w("ShareLinks", "Ignoring unparseable link", e)
            return null
        }

        if (!"https".equals(uri.scheme, ignoreCase = true)) return null
        val host = uri.host?.lowercase() ?: return null
        if (host !in LINK_HOSTS) return null

        // ["", "post", "<id>"] for /post/<id>, plus a trailing "" for a
        // trailing slash. Anything longer is a route we don't claim.
        val segments = (uri.path ?: "").split("/").toMutableList()
        if (segments.isNotEmpty() && segments.last().isEmpty()) segments.removeAt(segments.size - 1)
        if (segments.size != 3 || segments[0].isNotEmpty() || segments[1] != "post") return null

        val postIdentifier = segments[2]
        if (postIdentifier.isEmpty()) return null

        // URI decodes the fragment, matching what commentUrl encoded.
        val fragment = uri.fragment
        val commentIdentifier = fragment
            ?.takeIf { it.startsWith(COMMENT_FRAGMENT_PREFIX) }
            ?.removePrefix(COMMENT_FRAGMENT_PREFIX)
            ?.takeIf { it.isNotEmpty() }

        return SharedPostLink(postIdentifier, commentIdentifier)
    }

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
