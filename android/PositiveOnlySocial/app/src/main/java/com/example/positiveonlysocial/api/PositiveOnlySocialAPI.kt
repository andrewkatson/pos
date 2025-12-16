package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.*
import retrofit2.Response
import retrofit2.http.*

interface PositiveOnlySocialAPI {

    // =============================================================================
    // AUTHENTICATION
    // =============================================================================

    @POST("login")
    suspend fun loginUser(@Body request: LoginRequest): Response<AuthResponse>

    @POST("login/remember")
    suspend fun loginUserWithRememberMe(@Body request: TokenRefreshRequest): Response<TokenRefreshResponse>

    @POST("register")
    suspend fun register(@Body request: RegisterRequest): Response<AuthResponse>

    @POST("logout")
    suspend fun logout(@Header("Authorization") token: String): Response<GenericResponse>

    @POST("user/delete/")
    suspend fun deleteUser(@Header("Authorization") token: String): Response<GenericResponse>

    @POST("verify-identity/")
    suspend fun verifyIdentity(
        @Header("Authorization") token: String,
        @Body request: IdentityVerificationRequest
    ): Response<GenericResponse>

    // ============================================================================================
    // PASSWORD RESET
    // ============================================================================================

    @POST("password/request-reset")
    suspend fun requestReset(@Body request: ResetRequest): Response<GenericResponse>

    @GET("password/verify-reset/{username_or_email}/{reset_id}")
    suspend fun verifyReset(
        @Path("username_or_email") usernameOrEmail: String,
        @Path("reset_id") resetId: Int
    ): Response<GenericResponse>

    @POST("password/reset")
    suspend fun resetPassword(@Body request: PasswordResetSubmitRequest): Response<GenericResponse>

    // ============================================================================================
    // FEED / RETRIEVAL
    // ============================================================================================

    @GET("feed/")
    suspend fun getPostsInFeed(
        @Header("Authorization") token: String,
        @Query("batch") batch: Int
    ): Response<List<Post>>

    @GET("feed/following/")
    suspend fun getFollowedPosts(
        @Header("Authorization") token: String,
        @Query("batch") batch: Int
    ): Response<List<Post>>

    @GET("posts/user/{username}/")
    suspend fun getPostsForUser(
        @Header("Authorization") token: String,
        @Path("username") username: String,
        @Query("batch") batch: Int
    ): Response<List<Post>>

    @GET("posts/{post_id}/")
    suspend fun getPostDetails(
        @Path("post_id") postId: String
    ): Response<Post>

    // ============================================================================================
    // POSTS
    // ============================================================================================

    @POST("posts/create")
    suspend fun makePost(
        @Header("Authorization") token: String,
        @Body request: CreatePostRequest
    ): Response<CreatePostResponse>

    @POST("posts/{post_id}/delete/")
    suspend fun deletePost(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String
    ): Response<GenericResponse>

    @POST("posts/{post_id}/report/")
    suspend fun reportPost(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String,
        @Body request: ReportRequest
    ): Response<GenericResponse>

    @POST("posts/{post_id}/like/")
    suspend fun likePost(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String
    ): Response<GenericResponse>

    @POST("posts/{post_id}/unlike/")
    suspend fun unlikePost(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String
    ): Response<GenericResponse>

    // ============================================================================================
    // COMMENTS
    // ============================================================================================

    @POST("posts/{post_id}/comment/")
    suspend fun commentOnPost(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String,
        @Body request: CommentRequest
    ): Response<CommentResponse>

    @POST("posts/{post_id}/comment/{thread_id}/reply/")
    suspend fun replyToThread(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String,
        @Path("thread_id") threadId: String,
        @Body request: CommentRequest
    ): Response<CommentResponse>

    @POST("posts/{post_id}/comment/{thread_id}/comment/{comment_id}/like/")
    suspend fun likeComment(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String,
        @Path("thread_id") threadId: String,
        @Path("comment_id") commentId: String
    ): Response<GenericResponse>

    @POST("posts/{post_id}/comment/{thread_id}/comment/{comment_id}/unlike/")
    suspend fun unlikeComment(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String,
        @Path("thread_id") threadId: String,
        @Path("comment_id") commentId: String
    ): Response<GenericResponse>

    @POST("posts/{post_id}/comment/{thread_id}/comment/{comment_id}/delete/")
    suspend fun deleteComment(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String,
        @Path("thread_id") threadId: String,
        @Path("comment_id") commentId: String
    ): Response<GenericResponse>

    @POST("posts/{post_id}/comment/{thread_id}/comment/{comment_id}/report/")
    suspend fun reportComment(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String,
        @Path("thread_id") threadId: String,
        @Path("comment_id") commentId: String,
        @Body request: ReportRequest
    ): Response<GenericResponse>

    @GET("posts/{post_id}/comments/")
    suspend fun getCommentsForPost(
        @Path("post_id") postId: String,
        @Query("batch") batch: Int
    ): Response<List<CommentThreadDto>>

    @GET("comments/{thread_id}/")
    suspend fun getCommentsForThread(
        @Path("thread_id") threadId: String,
        @Query("batch") batch: Int
    ): Response<List<CommentDto>>

    // ============================================================================================
    // USER / PROFILE
    // ============================================================================================

    @GET("users/search/")
    suspend fun searchUsers(
        @Header("Authorization") token: String,
        @Query("fragment") fragment: String
    ): Response<List<User>>

    @POST("users/{username}/follow/")
    suspend fun followUser(
        @Header("Authorization") token: String,
        @Path("username") username: String
    ): Response<GenericResponse>

    @POST("users/{username}/unfollow/")
    suspend fun unfollowUser(
        @Header("Authorization") token: String,
        @Path("username") username: String
    ): Response<GenericResponse>

    @POST("users/{username}/block/")
    suspend fun toggleBlock(
        @Header("Authorization") token: String,
        @Path("username") username: String
    ): Response<GenericResponse>

    @GET("users/{username}/profile/")
    suspend fun getProfileDetails(
        @Header("Authorization") token: String,
        @Path("username") username: String
    ): Response<ProfileDetailsResponse>
}