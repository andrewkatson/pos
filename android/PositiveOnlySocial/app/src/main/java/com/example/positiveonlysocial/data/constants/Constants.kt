package com.example.positiveonlysocial.data.constants

object Constants {
    val isUnitTesting = false
    const val BASE_URL = "https://api.smiling.social/user_index/"

    // Maximum lengths for user-authored text, mirroring MAX_CAPTION_LENGTH /
    // MAX_COMMENT_LENGTH / MAX_BIO_LENGTH in backend/user_system/constants.py.
    const val MAX_CAPTION_LENGTH = 125
    const val MAX_COMMENT_LENGTH = 500
    const val MAX_BIO_LENGTH = 500

    // Error code the backend returns when the account has an active outright ban.
    const val ACCOUNT_BANNED = "account_banned"
    const val ACCOUNT_SUSPENDED_MESSAGE =
        "Your account has been suspended for violating our community guidelines."

    // Error code the backend returns when the account's email address is unverified.
    const val EMAIL_NOT_VERIFIED = "email_not_verified"
    const val EMAIL_NOT_VERIFIED_MESSAGE =
        "Please verify your email address first — check your inbox for the verification link."

    // Shown when a session was issued but couldn't be written to secure storage
    // (issue #503). Every screen reads the session back out of the keychain, so
    // an unpersisted session can't load anything — the user is told instead of
    // being dropped into an empty signed-in shell.
    const val SESSION_STORAGE_FAILED_MESSAGE =
        "We couldn't save your login on this device. Please try again, or restart the app if this keeps happening."

    // Shown on a screen whose data needs a session that isn't there.
    const val SESSION_MISSING_MESSAGE =
        "You're not signed in on this device anymore. Please sign in again."

    // Error code the backend returns from login/2fa/ when the challenge is gone
    // (expired, already used, or invalidated). A stable code like the two above,
    // so the login screen can drop back to the password form without depending
    // on backend wording. Mirrors login_user_2fa in the backend.
    const val INVALID_TWO_FACTOR_CHALLENGE = "invalid_two_factor_challenge"

    // Google sign-in (issue #10). Error codes login/google/ can answer with, and
    // the prose each maps to on the login screen.
    const val GOOGLE_SIGN_IN_UNAVAILABLE = "google_sign_in_unavailable"
    const val INVALID_GOOGLE_TOKEN = "invalid_google_token"
    const val GOOGLE_EMAIL_UNVERIFIED = "google_email_unverified"
    const val GOOGLE_SIGN_IN_UNAVAILABLE_MESSAGE =
        "Google sign-in isn't available right now. Please sign in with your password."
    const val GOOGLE_EMAIL_UNVERIFIED_MESSAGE =
        "Google hasn't verified the email address on that account, so we can't use it to sign you in."
    const val GOOGLE_EMAIL_AMBIGUOUS = "google_email_ambiguous"
    const val GOOGLE_EMAIL_AMBIGUOUS_MESSAGE =
        "More than one account already uses that email address. Please sign in with your password."
    const val GOOGLE_SIGN_IN_FAILED_MESSAGE = "Google sign-in failed. Please try again."

    // Support address shown under "Contact Us" in Settings for feedback and help
    // (issue #194). Distinct from the user's own contact info, which is loaded
    // from GET /me/.
    const val SUPPORT_EMAIL = "katsonsoftware@gmail.com"

    /** One section of the terms of service (issue #493). */
    data class TermsSection(val heading: String, val body: String)

    /** Shown above the terms so a reader can tell which version they accepted. */
    const val TERMS_OF_SERVICE_LAST_UPDATED = "August 13, 2026"

    /**
     * The terms of service, mirroring `website/src/termsOfService.ts` and
     * `GVOAppConstants.termsOfServiceSections` on iOS — the same duplication the
     * privacy policy below already lives with. The canonical public copy is
     * https://smiling.social/terms-of-service.
     */
    val TERMS_OF_SERVICE_SECTIONS = listOf(
        TermsSection(
            "Agreeing to these terms",
            "Good Vibes Only is a positivity-only social network. By creating an account, signing in — including with Google — or otherwise using the website or the mobile apps, you agree to these terms. If you do not agree to them, please do not use the service."
        ),
        TermsSection(
            "Who can use Good Vibes Only",
            "You must be at least 16 years old. Accounts belonging to 16- and 17-year-olds are kept in a separate visibility band from adult accounts, and the two never see each other’s posts, comments, or profiles. Give us accurate information, keep one account per person, and keep your password and any second factor to yourself — anything done from your account is treated as done by you. Tell us if you think someone else has got in."
        ),
        TermsSection(
            "What you may post",
            "Every post, comment, username, bio, and photo has to be positive or neutral: no swearing, nudity, sexually suggestive material, gore, hate speech, harassment, bullying, or misinformation, and no photos of babies, children, or anyone under 18. Content that starts sad but ends on a happy or hopeful note is welcome. You must hold the rights to whatever you upload, and you may not impersonate anyone, spam, run bots, or try to break, overload, or reverse-engineer the service."
        ),
        TermsSection(
            "How we moderate",
            "Submissions are checked automatically before they go up, and other users can report content and accounts. Anything that fails the guidelines is refused or hidden, and an account that breaks them can be warned, suspended for a time, banned permanently, or have its content hidden from other people without being told, where telling the holder would only help them evade enforcement. You can ask us to look again at anything of yours we hid from the “Hidden Content & Appeals” screen. Moderation is automated and imperfect in both directions, and the final call on what stays up is ours."
        ),
        TermsSection(
            "Your content stays yours",
            "You keep ownership of everything you post. You give us permission to store, reproduce, and display it for the purpose of running the service and showing it to the audience you chose. That permission ends when the content is deleted, apart from copies still sitting in backups or anything we are required to keep by law."
        ),
        TermsSection(
            "Signing in with Google",
            "If you sign in with Google, we receive the Google account’s verified email address and a permanent account identifier, and use them only to create or find your Good Vibes Only account. We never see your Google password and we ask for nothing else from your Google account. Your use of Google’s own services remains governed by Google’s terms and privacy policy; deleting your Good Vibes Only account ends the connection on our side."
        ),
        TermsSection(
            "Ending your account",
            "You can delete your account at any time from Settings, or from the account & data deletion page on the website without opening an app. Deleting removes your posts and their images, comments, likes, saved posts, follows, blocks, appeals, and sessions, and cannot be undone. We may suspend or terminate an account that breaks these terms or the content guidelines."
        ),
        TermsSection(
            "The service is provided as is",
            "Good Vibes Only is offered free of charge and as is, with no warranty of any kind. We may change, suspend, or discontinue any part of it, and to the fullest extent the law allows we are not liable for lost content or for any indirect or consequential loss. Nothing here takes away rights you have that cannot be given up under the law where you live."
        ),
        TermsSection(
            "Changes to these terms",
            "These terms will change as the service does. The date above marks the current version, and continuing to use Good Vibes Only after an update means you accept the updated terms."
        ),
        TermsSection(
            "Contact",
            "Questions about these terms, or anything else, can go to katsonsoftware@gmail.com."
        ),
    )

    const val PRIVACY_POLICY_TEXT =
        "We collect your username, email address, and password for authentication; your password is stored as a salted hash, never in plain text. We do not store your date of birth itself, only whether you are an adult and whether your identity has been verified, derived from it at signup. We store your posts, comments, and related metadata such as like counts and reports. We also track follower/following relationships and blocked users to maintain the social environment, and the IP address of your login sessions and known devices so we can alert you to logins from a new device."
}