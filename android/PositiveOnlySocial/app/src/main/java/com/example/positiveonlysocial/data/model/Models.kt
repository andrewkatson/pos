package com.example.positiveonlysocial.data.model

import com.google.gson.annotations.SerializedName
import java.util.Date

// --- Authentication DTOs ---

data class RegisterRequest(
    val username: String,
    val email: String,
    val password: String,
    @SerializedName("remember_me") val rememberMe: String,
    @SerializedName("remember_me") val rememberMe: String,
    val ip: String,
    @SerializedName("date_of_birth") val dateOfBirth: String
)

data class IdentityVerificationRequest(
    @SerializedName("date_of_birth") val dateOfBirth: String
)

data class AuthResponse(
    @SerializedName("session_management_token") val sessionToken: String,
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

data class PasswordResetSubmitRequest(
    val username: String,
    val email: String,
    val password: String
)

// --- Post DTOs ---

data class CreatePostRequest(
    @SerializedName("image_url") val imageUrl: String,
    val caption: String
)

data class CreatePostResponse(
    @SerializedName("post_identifier") val postIdentifier: String
)

data class ReportRequest(
    val reason: String
)

// Renamed from PostDto to Post to match Swift
data class Post(
    @SerializedName("post_identifier") val postIdentifier: String,
    @SerializedName("image_url") val imageUrl: String,
    val caption: String,
    @SerializedName("authorUsername") val authorUsername: String,
    val likeCount: Int? = 0
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
    @SerializedName("comment_likes") val likeCount: Int
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
    @SerializedName("following_count") val followingCount: Int,
    @SerializedName("is_following") val isFollowing: Boolean,
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
    val isIdentityVerified: Boolean,
    // Kept for internal Android logic if needed, but nullable
    val seriesIdentifier: String? = null,
    val loginCookieToken: String? = null
)

// --- View Data Models (Matching Swift) ---

data class PostDisplayData(
    val id: String, // postIdentifier
    val imageURL: String,
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
    val createdDate: Date // Using Date for now, might need conversion from String
)

data class CommentThreadViewData(
    val id: String,
    val comments: List<CommentViewData>
)