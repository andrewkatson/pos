package com.example.positiveonlysocial.fcm

/**
 * How a foreground push notification is keyed in the notification shade
 * (issues #444/#604).
 *
 * A rejection keeps a single slot (no tag). Each piece of activity gets its own
 * slot, tagged by kind plus what it is about — the post, or for follow activity
 * the person who acted — so a like doesn't replace a comment and one person's
 * follow doesn't replace another's, while a repeat of the same thing (a second
 * like on the same post) replaces the first rather than stacking.
 *
 * The full string is the key, never its hashCode: hashes collide for distinct
 * strings ("Aa" and "BB"), and usernames are user-chosen, so a hashed id would
 * let two people's notifications overwrite each other.
 */
object PushNotificationKeys {
    /** The notification tag for a payload, or null for a single-slot kind
     * (a rejection, or anything not on the Activity channel). */
    fun tagFor(type: String?, postId: String?, username: String?): String? {
        if (type == null || type !in PosFirebaseMessagingService.ACTIVITY_TYPES) return null
        val subject = postId ?: username ?: return type
        return "$type:$subject"
    }
}
