package com.example.positiveonlysocial.data.model

import com.google.gson.annotations.SerializedName

class Models {
}

// --- Authentication DTOs ---

data class RegisterRequest(
    val username: String,
    val email: String,
    val password: String,
    @SerializedName("remember_me") val rememberMe: String, // Backend expects string initially
    val ip: String
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

data class PostDto(
    @SerializedName("post_identifier") val postIdentifier: String,
    @SerializedName("image_url") val imageUrl: String,
    val caption: String,
    val username: String? = null, // Used in feed
    @SerializedName("author_username") val authorUsername: String? = null, // Used in profile
    @SerializedName("post_likes") val likeCount: Int? = null
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
    @SerializedName("creation_time") val creationTime: String, // Consider using Date/Instant
    @SerializedName("updated_time") val updatedTime: String,
    @SerializedName("comment_likes") val likeCount: Int
)

// --- User/Profile DTOs ---

data class UserSearchDto(
    val username: String,
    @SerializedName("identity_is_verified") val isVerified: Boolean
)

data class ProfileDto(
    val username: String,
    @SerializedName("post_count") val postCount: Int,
    @SerializedName("follower_count") val followerCount: Int,
    @SerializedName("following_count") val followingCount: Int,
    @SerializedName("is_following") val isFollowing: Boolean
)

// Generic success/error response
data class GenericResponse(
    val message: String?,
    val error: String?
)