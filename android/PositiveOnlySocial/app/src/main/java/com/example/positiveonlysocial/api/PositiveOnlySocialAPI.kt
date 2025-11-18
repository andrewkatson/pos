package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.*
import retrofit2.Response
import retrofit2.http.*

interface PositiveOnlySocialAPI {

    // =============================================================================
    // AUTHENTICATION
    // =============================================================================

    @POST("register")
    suspend fun register(@Body request: RegisterRequest): Response<AuthResponse>

    @POST("login_user")
    suspend fun login(@Body request: LoginRequest): Response<AuthResponse>

    @POST("login_user_with_remember_me")
    suspend fun loginWithRememberMe(@Body request: TokenRefreshRequest): Response<TokenRefreshResponse>

    @POST("logout_user")
    suspend fun logout(): Response<GenericResponse>

    @POST("delete_user")
    suspend fun deleteUser(): Response<GenericResponse>

    // =============================================================================
    // PASSWORD RESET
    // =============================================================================

    @POST("request_reset")
    suspend fun requestReset(@Body request: ResetRequest): Response<GenericResponse>

    // Corresponds to: verify_reset(request, username_or_email, reset_id)
    @GET("verify_reset/{username_or_email}/{reset_id}")
    suspend fun verifyReset(
        @Path("username_or_email") usernameOrEmail: String,
        @Path("reset_id") resetId: Int
    ): Response<GenericResponse>

    @POST("reset_password")
    suspend fun resetPassword(@Body request: PasswordResetSubmitRequest): Response<GenericResponse>

    // =============================================================================
    // POSTS
    // =============================================================================

    @POST("make_post")
    suspend fun makePost(@Body request: CreatePostRequest): Response<CreatePostResponse>

    @POST("delete_post/{post_identifier}")
    suspend fun deletePost(@Path("post_identifier") postId: String): Response<GenericResponse>

    @POST("report_post/{post_identifier}")
    suspend fun reportPost(
        @Path("post_identifier") postId: String,
        @Body request: ReportRequest
    ): Response<GenericResponse>

    @POST("like_post/{post_identifier}")
    suspend fun likePost(@Path("post_identifier") postId: String): Response<GenericResponse>

    @POST("unlike_post/{post_identifier}")
    suspend fun unlikePost(@Path("post_identifier") postId: String): Response<GenericResponse>

    // =============================================================================
    // FEED / RETRIEVAL
    // =============================================================================

    @GET("get_posts_in_feed")
    suspend fun getPostsInFeed(@Query("batch") batch: Int): Response<List<PostDto>>

    @GET("get_posts_for_followed_users")
    suspend fun getFollowedPosts(@Query("batch") batch: Int): Response<List<PostDto>>

    // Corresponds to: get_posts_for_user(request, username, batch)
    @GET("get_posts_for_user/{username}")
    suspend fun getPostsForUser(
        @Path("username") username: String,
        @Query("batch") batch: Int
    ): Response<List<PostDto>>

    @GET("get_post_details/{post_identifier}")
    suspend fun getPostDetails(@Path("post_identifier") postId: String): Response<PostDto>

    // =============================================================================
    // COMMENTS
    // =============================================================================

    @POST("comment_on_post/{post_identifier}")
    suspend fun commentOnPost(
        @Path("post_identifier") postId: String,
        @Body request: CommentRequest
    ): Response<CommentResponse>

    @POST("reply_to_comment_thread/{post_identifier}/{thread_identifier}")
    suspend fun replyToThread(
        @Path("post_identifier") postId: String,
        @Path("thread_identifier") threadId: String,
        @Body request: CommentRequest
    ): Response<CommentResponse>

    @POST("like_comment/{post_identifier}/{thread_identifier}/{comment_identifier}")
    suspend fun likeComment(
        @Path("post_identifier") postId: String,
        @Path("thread_identifier") threadId: String,
        @Path("comment_identifier") commentId: String
    ): Response<GenericResponse>

    @POST("unlike_comment/{post_identifier}/{thread_identifier}/{comment_identifier}")
    suspend fun unlikeComment(
        @Path("post_identifier") postId: String,
        @Path("thread_identifier") threadId: String,
        @Path("comment_identifier") commentId: String
    ): Response<GenericResponse>

    @POST("delete_comment/{post_identifier}/{thread_identifier}/{comment_identifier}")
    suspend fun deleteComment(
        @Path("post_identifier") postId: String,
        @Path("thread_identifier") threadId: String,
        @Path("comment_identifier") commentId: String
    ): Response<GenericResponse>

    @POST("report_comment/{post_identifier}/{thread_identifier}/{comment_identifier}")
    suspend fun reportComment(
        @Path("post_identifier") postId: String,
        @Path("thread_identifier") threadId: String,
        @Path("comment_identifier") commentId: String,
        @Body request: ReportRequest
    ): Response<GenericResponse>

    @GET("get_comments_for_post/{post_identifier}")
    suspend fun getCommentsForPost(
        @Path("post_identifier") postId: String,
        @Query("batch") batch: Int
    ): Response<List<CommentThreadDto>>

    @GET("get_comments_for_thread/{thread_identifier}")
    suspend fun getCommentsForThread(
        @Path("thread_identifier") threadId: String,
        @Query("batch") batch: Int
    ): Response<List<CommentDto>>

    // =============================================================================
    // USER / PROFILE
    // =============================================================================

    @GET("get_users_matching_fragment/{fragment}")
    suspend fun searchUsers(@Path("fragment") fragment: String): Response<List<UserSearchDto>>

    @POST("follow_user/{username}")
    suspend fun followUser(@Path("username") username: String): Response<GenericResponse>

    @POST("unfollow_user/{username}")
    suspend fun unfollowUser(@Path("username") username: String): Response<GenericResponse>

    @GET("get_profile_details/{username}")
    suspend fun getProfileDetails(@Path("username") username: String): Response<ProfileDto>
}