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

// --- Post DTOs ---

data class CreatePostRequest(
    // Null for a text-only post (#307); Gson omits null fields from the body.
    @SerializedName("image_url") val imageUrl: String? = null,
    val caption: String
)

data class CreatePostResponse(
    @SerializedName("post_identifier") val postIdentifier: String,
    // Present (true) when the post was created hidden pending appeal — the
    // classifier flagged it but the rejection is appealable. Absent/false for
    // a normal post.
    val hidden: Boolean = false,
    @SerializedName("hidden_reason") val hiddenReason: String? = null,
    val message: String? = null
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
    // Only the post-details endpoint returns the like count (as "post_likes");
    // feed endpoints omit it, so it defaults to 0.
    @SerializedName("post_likes") val likeCount: Int? = 0,
    // Whether the current user has liked this post. Only the post-details endpoint
    // populates this; feed endpoints omit it, so it defaults to false.
    @SerializedName("is_liked") val isLiked: Boolean = false,
    // The full-resolution original image URL, used as a fallback when the
    // compressed `imageUrl` fails to load. The compressed copy is produced by an
    // async Lambda, so a just-posted (or recently hidden-pending-appeal) image may
    // not exist in the compressed bucket yet; without this fallback those grid
    // tiles render as empty black boxes until the user re-logs in (issues #252/#254).
    // Feed/details endpoints that predate the field omit it, so it defaults to null.
    @SerializedName("original_image_url") val originalImageUrl: String? = null
)

// --- Comment DTOs ---

data class CommentRequest(
    @SerializedName("comment_text") val commentText: String
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
    @SerializedName("is_liked") val isLiked: Boolean = false
)

// --- User/Profile DTOs ---

// Renamed from UserSearchDto to User to match Swift
data class User(
    val username: String,
    @SerializedName("identity_is_verified") val identityIsVerified: Boolean
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
    @SerializedName("is_adult") val isAdult: Boolean = false
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
    val authorUsername: String
)

data class CommentViewData(
    val id: String, // commentIdentifier
    val threadId: String, // commentThreadIdentifier
    val authorUsername: String,
    val body: String,
    val likeCount: Int,
    val isLiked: Boolean, // Whether the current user has liked this comment
    val createdDate: Date // Using Date for now, might need conversion from String
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
    @SerializedName("has_appeal") val hasAppeal: Boolean = false
)

/** One of the signed-in user's hidden comments. */
data class HiddenComment(
    @SerializedName("comment_identifier") val commentIdentifier: String,
    val body: String,
    @SerializedName("hidden_reason") val hiddenReason: String = "",
    @SerializedName("has_appeal") val hasAppeal: Boolean = false
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
