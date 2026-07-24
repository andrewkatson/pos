package com.example.positiveonlysocial.data.model

import com.google.gson.annotations.SerializedName
import java.util.Date

// --- Authentication DTOs ---

data class RegisterRequest(
    val username: String,
    val email: String,
    val password: String,
    @SerializedName("remember_me") val rememberMe: String,
    val ip: String,
    @SerializedName("date_of_birth") val dateOfBirth: String
)

data class IdentityVerificationRequest(
    @SerializedName("date_of_birth") val dateOfBirth: String
)

data class AuthResponse(
    @SerializedName("session_management_token") val sessionToken: String,
    val username: String?,
    @SerializedName("user_id") val userId: String?,
    @SerializedName("series_identifier") val seriesIdentifier: String?,
    @SerializedName("login_cookie_token") val loginCookieToken: String?
)

data class LoginRequest(
    @SerializedName("username_or_email") val usernameOrEmail: String,
    val password: String,
    @SerializedName("remember_me") val rememberMe: String,
    val ip: String
)

// --- Two-Factor Authentication DTOs (issue #348) ---

/**
 * The login response, which is one of two shapes: a session (same fields as
 * AuthResponse) for ordinary accounts, or — when the account has two-factor
 * authentication enabled — `twoFactorRequired` plus a short-lived
 * `challengeToken` to exchange at login/2fa/. Every field is nullable so Gson
 * can decode either shape safely.
 */
data class LoginResponse(
    @SerializedName("two_factor_required") val twoFactorRequired: Boolean = false,
    @SerializedName("challenge_token") val challengeToken: String? = null,
    @SerializedName("session_management_token") val sessionToken: String? = null,
    val username: String? = null,
    @SerializedName("user_id") val userId: String? = null,
    @SerializedName("series_identifier") val seriesIdentifier: String? = null,
    @SerializedName("login_cookie_token") val loginCookieToken: String? = null
)

/** Second login step: exactly one of totpCode / recoveryCode is set (Gson omits nulls). */
data class LoginTwoFactorRequest(
    @SerializedName("challenge_token") val challengeToken: String,
    @SerializedName("totp_code") val totpCode: String? = null,
    @SerializedName("recovery_code") val recoveryCode: String? = null
)

data class TotpSetupResponse(
    // Base32 TOTP secret, for manual entry into an authenticator app.
    @SerializedName("totp_secret") val totpSecret: String,
    // otpauth:// provisioning URI, rendered as a QR code for scanning.
    @SerializedName("otpauth_uri") val otpauthUri: String
)

/**
 * Confirming requires the password as well as the code: a stolen session alone
 * must not be able to bind an attacker's authenticator, which would hand them
 * the recovery codes and lock the real owner out for good.
 */
data class ConfirmTotpRequest(
    @SerializedName("password") val password: String,
    @SerializedName("totp_code") val totpCode: String
)

data class ConfirmTotpResponse(
    @SerializedName("totp_enabled") val totpEnabled: Boolean,
    // Single-use recovery codes, shown exactly once at enrollment.
    @SerializedName("recovery_codes") val recoveryCodes: List<String>
)

/** Disabling requires the password plus exactly one of the two code kinds. */
data class DisableTotpRequest(
    val password: String,
    @SerializedName("totp_code") val totpCode: String? = null,
    @SerializedName("recovery_code") val recoveryCode: String? = null
)

data class DisableTotpResponse(
    @SerializedName("totp_enabled") val totpEnabled: Boolean
)

/** The signed-in account's own contact details, from `GET /me/` (issue #197/#194). */
data class CurrentUserResponse(
    @SerializedName("username") val username: String,
    @SerializedName("email") val email: String
)

/**
 * Changing the password requires the current password as well as the session,
 * mirroring the backend (issue #197): a stolen session alone must not be able to
 * change it. On success the backend evicts the account's other sessions.
 */
data class ChangePasswordRequest(
    @SerializedName("password") val password: String,
    @SerializedName("new_password") val newPassword: String
)

data class TokenRefreshRequest(
    @SerializedName("session_management_token") val sessionToken: String,
    @SerializedName("series_identifier") val seriesIdentifier: String,
    @SerializedName("login_cookie_token") val loginCookieToken: String,
    val ip: String
)

data class TokenRefreshResponse(
    @SerializedName("login_cookie_token") val newLoginCookieToken: String,
    @SerializedName("session_management_token") val newSessionToken: String
)

// --- Password Reset DTOs ---

data class ResetRequest(
    @SerializedName("username_or_email") val usernameOrEmail: String
)

data class VerificationRequest(
    @SerializedName("username_or_email") val usernameOrEmail: String,
    @SerializedName("verification_token") val verificationToken: String
)

data class PasswordResetSubmitRequest(
    val username: String,
    val email: String,
    val password: String,
    @SerializedName("reset_token") val resetToken: String
)

data class VerifyResetResponse(
    val message: String?,
    val error: String?,
    @SerializedName("reset_token") val resetToken: String?
)

// --- Email Verification DTOs ---

data class VerifyEmailRequest(
    @SerializedName("verification_token") val verificationToken: String
)

data class ResendVerificationEmailRequest(
    @SerializedName("username_or_email") val usernameOrEmail: String
)

// --- Post DTOs ---

/**
 * One inline-formatting span over a comment's plain `body` (issue #318).
 * Offsets are UTF-16 code-unit indices (matching Kotlin/JS string indexing and
 * the backend contract): `0 <= start < end <= body.length`. Spans are sorted
 * and non-overlapping. The plain `body` is never modified — formatting is
 * separate metadata, so moderation still classifies plain text.
 */
data class CommentFormatSpan(
    val start: Int,
    val end: Int,
    val bold: Boolean = false,
    val italic: Boolean = false,
    // One of "small", "normal", "large", "xlarge".
    val size: String = "normal"
)

data class CreatePostRequest(
    // Null for a text-only post (#307); Gson omits null fields from the body.
    @SerializedName("image_url") val imageUrl: String? = null,
    val caption: String,
    // Whole-caption font + whole-tile background color keys (issue #318).
    @SerializedName("caption_font") val captionFont: String = "default",
    @SerializedName("background_color") val backgroundColor: String = "default"
)

data class CreatePostResponse(
    @SerializedName("post_identifier") val postIdentifier: String,
    // "pending" on current backends: classification runs asynchronously
    // (issue #282) and the outcome is reconciled via getPostStatus or a grid
    // refresh. Null on older backends, which classified inline.
    val status: String? = null,
    // True when the post was created hidden — pending classification on
    // current backends, or hidden pending appeal on older inline-classifying
    // ones.
    val hidden: Boolean = false,
    @SerializedName("hidden_reason") val hiddenReason: String? = null,
    val message: String? = null
)

/**
 * Response of the author-only post-status endpoint (issue #282): "pending",
 * "approved", "rejected", or "rejected_final", with a user-facing message for
 * the non-approved states.
 */
data class PostStatusResponse(
    @SerializedName("post_identifier") val postIdentifier: String,
    val status: String,
    @SerializedName("reason_code") val reasonCode: String? = null,
    val appealable: Boolean = false,
    val hidden: Boolean = false,
    @SerializedName("hidden_reason") val hiddenReason: String? = null,
    val message: String? = null
)

data class CreateUploadUrlResponse(
    // Short-lived presigned S3 PUT URL to send the JPEG bytes to.
    @SerializedName("upload_url") val uploadUrl: String,
    // The canonical object URL (no signing query) to pass to makePost.
    @SerializedName("image_url") val imageUrl: String
)

data class ReportRequest(
    val reason: String
)

// Renamed from PostDto to Post to match Swift
data class Post(
    @SerializedName("post_identifier") val postIdentifier: String,
    // Null for a text-only post (#307), which renders as a caption tile.
    @SerializedName("image_url") val imageUrl: String? = null,
    val caption: String,
    @SerializedName("author_username") val authorUsername: String,
    // The like count, and whether the current user has liked / reported this post
    // (plus their own report reason, so the retract dialog can show it
    // pre-populated — issue #176).
    //
    // The post-details endpoint has always returned these; the three post-listing
    // endpoints (feed, followed feed, a user's posts) now return them too, so a
    // post can be liked, reported, un-reported and deleted straight from a list
    // (issue #267). They stay nullable/defaulted so a response from an older
    // server, which omits them, still parses.
    @SerializedName("post_likes") val likeCount: Int? = 0,
    @SerializedName("is_liked") val isLiked: Boolean = false,
    @SerializedName("is_reported") val isReported: Boolean = false,
    @SerializedName("report_reason") val reportReason: String? = null,
    // How many comments on this post are visible to the viewer. Shown on the feed
    // rows, where tapping it opens the post (issue #249). Defaults to 0 for
    // responses that predate the field.
    @SerializedName("comment_count") val commentCount: Int? = 0,
    // The full-resolution original image URL, used as a fallback when the
    // compressed `imageUrl` fails to load. The compressed copy is produced by an
    // async Lambda, so a just-posted (or recently hidden-pending-appeal) image may
    // not exist in the compressed bucket yet; without this fallback those grid
    // tiles render as empty black boxes until the user re-logs in (issues #252/#254).
    // Feed/details endpoints that predate the field omit it, so it defaults to null.
    @SerializedName("original_image_url") val originalImageUrl: String? = null,
    // When the post was created (ISO-8601 from the real backend, epoch-millis
    // from the stub — see parseBackendDate). Returned by the post-details
    // endpoint and, since issue #249, by the post-listing endpoints too, so the
    // feed rows can show how long ago a post was made. Null for responses that
    // predate the field, in which case the label is simply omitted.
    @SerializedName("creation_time") val creationTime: String? = null,
    // Author-only classification state (issue #282): present on the viewer's
    // own posts so grids can render pending/rejected states. Other users'
    // posts never carry these (their pending/hidden posts are filtered out
    // server-side entirely). One of "pending", "approved", "rejected",
    // "rejected_final"; null on older backends or others' posts.
    val status: String? = null,
    val hidden: Boolean? = null,
    @SerializedName("hidden_reason") val hiddenReason: String? = null,
    val appealable: Boolean? = null,
    // The author's approved profile photo (issue #7), threaded next to
    // author_username through every list/detail payload. Compressed variant with
    // a full-resolution fallback, mirroring image_url/original_image_url; both
    // null when the author has no approved photo, and absent (defaulting to null)
    // on responses that predate the field.
    @SerializedName("author_profile_image_url") val authorProfileImageUrl: String? = null,
    @SerializedName("author_profile_image_original_url") val authorProfileImageOriginalUrl: String? = null,
    // Whole-caption font + whole-tile background color keys (issue #318). At the
    // end of the list so existing positional constructions are unaffected.
    // Nullable because Gson does not apply Kotlin default values for absent JSON
    // fields (an older response omitting them yields null); the render layer
    // treats null as "default".
    @SerializedName("caption_font") val captionFont: String? = null,
    @SerializedName("background_color") val backgroundColor: String? = null
)

// --- Comment DTOs ---

data class CommentRequest(
    @SerializedName("comment_text") val commentText: String,
    // Inline formatting spans (issue #318); null omits the field from the body.
    @SerializedName("body_formatting") val bodyFormatting: List<CommentFormatSpan>? = null
)

data class CommentResponse(
    @SerializedName("comment_thread_identifier") val threadIdentifier: String? = null,
    @SerializedName("comment_identifier") val commentIdentifier: String
)

data class CommentThreadDto(
    @SerializedName("comment_thread_identifier") val threadIdentifier: String
)

data class CommentDto(
    @SerializedName("comment_identifier") val commentIdentifier: String,
    val body: String,
    @SerializedName("author_username") val authorUsername: String,
    @SerializedName("creation_time") val creationTime: String,
    @SerializedName("updated_time") val updatedTime: String,
    @SerializedName("comment_likes") val likeCount: Int,
    @SerializedName("is_liked") val isLiked: Boolean = false,
    // Whether the current user has an active report against this comment, plus
    // their own report reason for the pre-populated retract dialog (issue #176).
    @SerializedName("is_reported") val isReported: Boolean = false,
    @SerializedName("report_reason") val reportReason: String? = null,
    // The comment author's approved profile photo (issue #7), same
    // compressed→original convention as posts; null when they have no photo.
    @SerializedName("author_profile_image_url") val authorProfileImageUrl: String? = null,
    @SerializedName("author_profile_image_original_url") val authorProfileImageOriginalUrl: String? = null,
    // Inline formatting spans over `body` (issue #318); null = plain text. At
    // the end with a default so existing positional constructions are unaffected.
    @SerializedName("body_formatting") val bodyFormatting: List<CommentFormatSpan>? = null
)

// --- User/Profile DTOs ---

// Renamed from UserSearchDto to User to match Swift
data class User(
    val username: String,
    @SerializedName("identity_is_verified") val identityIsVerified: Boolean,
    // The user's approved profile photo (issue #7), returned by search and the
    // blocked-users list so their avatar shows next to the name; null when they
    // have no approved photo, and absent on responses that predate the field.
    @SerializedName("author_profile_image_url") val authorProfileImageUrl: String? = null,
    @SerializedName("author_profile_image_original_url") val authorProfileImageOriginalUrl: String? = null
)

// Renamed from ProfileDto to ProfileDetailsResponse to match Swift
data class ProfileDetailsResponse(
    val username: String,
    @SerializedName("post_count") val postCount: Int,
    @SerializedName("follower_count") val followerCount: Int,
    @SerializedName("following_count") val followingCount: Int,
    @SerializedName("is_following") val isFollowing: Boolean,
    @SerializedName("is_blocked") val isBlocked: Boolean = false,
    @SerializedName("identity_is_verified") val identityIsVerified: Boolean = false,
    @SerializedName("is_adult") val isAdult: Boolean = false,
    // The profile owner's approved photo (issue #7): compressed variant with a
    // full-resolution fallback, shown as the large header avatar and (for
    // others) everywhere their name appears. Null when there is no approved photo.
    @SerializedName("profile_image_url") val profileImageUrl: String? = null,
    @SerializedName("profile_image_original_url") val profileImageOriginalUrl: String? = null,
    // Owner-only moderation state, present only when viewing your own profile
    // (the backend omits these for everyone else). profileImageStatus is one of
    // "none"|"pending"|"approved"|"rejected"; pendingProfileImageUrl is the
    // not-yet-approved upload the owner previews immediately.
    @SerializedName("profile_image_status") val profileImageStatus: String? = null,
    @SerializedName("profile_image_reason_code") val profileImageReasonCode: String? = null,
    @SerializedName("pending_profile_image_url") val pendingProfileImageUrl: String? = null
)

// --- Profile Photo DTOs (issue #7) ---

/**
 * Sets the signed-in user's profile photo. The JPEG bytes are uploaded first
 * via the presigned post-image pipeline (createUploadUrl + ImageUploader), and
 * this carries the canonical object URL that flow returns.
 */
data class SetProfilePhotoRequest(
    @SerializedName("image_url") val imageUrl: String
)

/**
 * Response of `POST profile/photo/` (HTTP 202). The photo is classified
 * asynchronously, so this always reports the initial "pending" state; the
 * approved/rejected outcome is read back from a subsequent getProfileDetails.
 */
data class SetProfilePhotoResponse(
    @SerializedName("profile_image_status") val profileImageStatus: String,
    val message: String? = null
)

/** Response of `POST profile/photo/remove/` (HTTP 200): status returns to "none". */
data class RemoveProfilePhotoResponse(
    @SerializedName("profile_image_status") val profileImageStatus: String,
    val message: String? = null
)

// Generic success/error response
data class GenericResponse(
    val message: String?,
    val error: String?
)

/**
 * Represents the user's persisted session data.
 * Updated to match Swift's UserSession struct.
 */
data class UserSession(
    val sessionToken: String,
    val username: String,
    val userId: String,
    val isIdentityVerified: Boolean,
    // Kept for internal Android logic if needed, but nullable
    val seriesIdentifier: String? = null,
    val loginCookieToken: String? = null
)

/**
 * "Remember Me" tokens persisted to the keychain after a successful login so the
 * app can silently re-authenticate via the remember-me endpoint on next launch.
 *
 * The field names are part of the persisted (gson) format and are read back in
 * [com.example.positiveonlysocial.ui.auth.WelcomeScreen] — keep them in sync.
 */
data class RememberMeTokens(val seriesId: String, val cookieToken: String)

// --- View Data Models (Matching Swift) ---

data class PostDisplayData(
    val id: String, // postIdentifier
    // Null for a text-only post (#307).
    val imageURL: String?,
    val caption: String,
    val likeCount: Int,
    val authorUsername: String,
    // Caption font + background color keys (issue #318); "default" is normal.
    val captionFont: String = "default",
    val backgroundColor: String = "default"
)

data class CommentViewData(
    val id: String, // commentIdentifier
    val threadId: String, // commentThreadIdentifier
    val authorUsername: String,
    val body: String,
    val likeCount: Int,
    val isLiked: Boolean, // Whether the current user has liked this comment
    val createdDate: Date, // Using Date for now, might need conversion from String
    // Whether the current user has an active report against this comment, and
    // their reason so the retract dialog can pre-populate it (issue #176).
    val isReported: Boolean = false,
    val reportReason: String? = null,
    // The comment author's approved profile photo (issue #7), for the avatar in
    // the comment row; null when they have no photo.
    val authorProfileImageUrl: String? = null,
    val authorProfileImageOriginalUrl: String? = null,
    // Inline formatting spans over `body` (issue #318); null = plain text. At
    // the end with a default so existing positional constructions are unaffected.
    val formatting: List<CommentFormatSpan>? = null
)

data class CommentThreadViewData(
    val id: String,
    val comments: List<CommentViewData>
)
// =============================================================================
// APPEALS (backend appeal endpoints)
// =============================================================================

/** One of the signed-in user's hidden posts, from the appeals endpoint. */
data class HiddenPost(
    @SerializedName("post_identifier") val postIdentifier: String,
    // Null for a text-only post (#307).
    @SerializedName("image_url") val imageUrl: String? = null,
    val caption: String,
    @SerializedName("hidden_reason") val hiddenReason: String = "",
    @SerializedName("has_appeal") val hasAppeal: Boolean = false,
    // Caption font + background color keys (issue #318); nullable because Gson
    // does not apply Kotlin defaults for absent JSON fields. The render layer
    // treats null as "default".
    @SerializedName("caption_font") val captionFont: String? = null,
    @SerializedName("background_color") val backgroundColor: String? = null
)

/** One of the signed-in user's hidden comments. */
data class HiddenComment(
    @SerializedName("comment_identifier") val commentIdentifier: String,
    val body: String,
    @SerializedName("hidden_reason") val hiddenReason: String = "",
    @SerializedName("has_appeal") val hasAppeal: Boolean = false,
    // Inline formatting spans over `body` (issue #318); null = plain text.
    @SerializedName("body_formatting") val bodyFormatting: List<CommentFormatSpan>? = null
)

/** An appeal the signed-in user has filed, with its current status. */
data class MyAppeal(
    @SerializedName("appeal_identifier") val appealIdentifier: String,
    @SerializedName("target_type") val targetType: String?,
    val status: String,
    val reason: String,
    @SerializedName("content_snapshot") val contentSnapshot: String?,
    @SerializedName("resolution_note") val resolutionNote: String?
)

data class SubmitAppealRequest(
    @SerializedName("target_type") val targetType: String,
    @SerializedName("target_identifier") val targetIdentifier: String,
    val reason: String
)

data class SubmitAppealResponse(
    @SerializedName("appeal_identifier") val appealIdentifier: String
)
