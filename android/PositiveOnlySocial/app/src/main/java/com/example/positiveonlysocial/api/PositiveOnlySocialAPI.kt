package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.*
import retrofit2.Response
import retrofit2.http.*

interface PositiveOnlySocialAPI {

    // =============================================================================
    // AUTHENTICATION
    // =============================================================================

    @POST("login/")
    suspend fun loginUser(@Body request: LoginRequest): Response<AuthResponse>

    @POST("login/remember/")
    suspend fun loginUserWithRememberMe(@Body request: TokenRefreshRequest): Response<TokenRefreshResponse>

    @POST("register/")
    suspend fun register(@Body request: RegisterRequest): Response<AuthResponse>

    @POST("logout/")
    suspend fun logout(@Header("Authorization") token: String): Response<GenericResponse>

    @POST("user/delete/")
    suspend fun deleteUser(@Header("Authorization") token: String): Response<GenericResponse>

    @POST("verify-identity/")
    suspend fun verifyIdentity(
        @Header("Authorization") token: String,
        @Body request: IdentityVerificationRequest
    ): Response<GenericResponse>

    // ============================================================================================
    // EMAIL VERIFICATION
    // ============================================================================================

    @POST("verify-email/")
    suspend fun verifyEmail(@Body request: VerifyEmailRequest): Response<GenericResponse>

    @POST("resend-verification-email/")
    suspend fun resendVerificationEmail(@Body request: ResendVerificationEmailRequest): Response<GenericResponse>

    // ============================================================================================
    // PASSWORD RESET
    // ============================================================================================

    @POST("password/request-reset/")
    suspend fun requestReset(@Body request: ResetRequest): Response<GenericResponse>

    @POST("password/verify-reset/")
    suspend fun verifyReset(@Body request: VerificationRequest): Response<VerifyResetResponse>

    @POST("password/reset/")
    suspend fun resetPassword(@Body request: PasswordResetSubmitRequest): Response<GenericResponse>

    // ============================================================================================
    // FEED / RETRIEVAL
    // ============================================================================================

    @GET("feed/{batch}/")
    suspend fun getPostsInFeed(
        @Header("Authorization") token: String,
        @Path("batch") batch: Int
    ): Response<List<Post>>

    @GET("feed/followed/{batch}/")
    suspend fun getFollowedPosts(
        @Header("Authorization") token: String,
        @Path("batch") batch: Int
    ): Response<List<Post>>

    @GET("users/{username}/posts/{batch}/")
    suspend fun getPostsForUser(
        @Header("Authorization") token: String,
        @Path("username") username: String,
        @Path("batch") batch: Int
    ): Response<List<Post>>

    @GET("posts/{post_id}/details/")
    suspend fun getPostDetails(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String
    ): Response<Post>

    // ============================================================================================
    // POSTS
    // ============================================================================================

    @POST("posts/upload-url/")
    suspend fun createUploadUrl(
        @Header("Authorization") token: String
    ): Response<CreateUploadUrlResponse>

    @POST("posts/create/")
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

    @POST("posts/{post_id}/report/retract/")
    suspend fun retractReportPost(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String
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

    @POST("posts/{post_id}/threads/{thread_id}/reply/")
    suspend fun replyToThread(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String,
        @Path("thread_id") threadId: String,
        @Body request: CommentRequest
    ): Response<CommentResponse>

    @POST("posts/{post_id}/threads/{thread_id}/comments/{comment_id}/like/")
    suspend fun likeComment(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String,
        @Path("thread_id") threadId: String,
        @Path("comment_id") commentId: String
    ): Response<GenericResponse>

    @POST("posts/{post_id}/threads/{thread_id}/comments/{comment_id}/unlike/")
    suspend fun unlikeComment(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String,
        @Path("thread_id") threadId: String,
        @Path("comment_id") commentId: String
    ): Response<GenericResponse>

    @POST("posts/{post_id}/threads/{thread_id}/comments/{comment_id}/delete/")
    suspend fun deleteComment(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String,
        @Path("thread_id") threadId: String,
        @Path("comment_id") commentId: String
    ): Response<GenericResponse>

    @POST("posts/{post_id}/threads/{thread_id}/comments/{comment_id}/report/")
    suspend fun reportComment(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String,
        @Path("thread_id") threadId: String,
        @Path("comment_id") commentId: String,
        @Body request: ReportRequest
    ): Response<GenericResponse>

    @POST("posts/{post_id}/threads/{thread_id}/comments/{comment_id}/report/retract/")
    suspend fun retractReportComment(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String,
        @Path("thread_id") threadId: String,
        @Path("comment_id") commentId: String
    ): Response<GenericResponse>

    @GET("posts/{post_id}/comments/{batch}/")
    suspend fun getCommentsForPost(
        @Header("Authorization") token: String,
        @Path("post_id") postId: String,
        @Path("batch") batch: Int
    ): Response<List<CommentThreadDto>>

    @GET("threads/{thread_id}/comments/{batch}/")
    suspend fun getCommentsForThread(
        @Header("Authorization") token: String,
        @Path("thread_id") threadId: String,
        @Path("batch") batch: Int
    ): Response<List<CommentDto>>

    // ============================================================================================
    // USER / PROFILE
    // ============================================================================================

    @GET("users/search/{fragment}/")
    suspend fun searchUsers(
        @Header("Authorization") token: String,
        @Path("fragment") fragment: String
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

    @GET("users/blocked/")
    suspend fun getBlockedUsers(
        @Header("Authorization") token: String
    ): Response<List<User>>

    @GET("users/{username}/profile/")
    suspend fun getProfileDetails(
        @Header("Authorization") token: String,
        @Path("username") username: String
    ): Response<ProfileDetailsResponse>

    // ============================================================================================
    // APPEALS
    // ============================================================================================

    @GET("appeals/hidden/posts/{batch}/")
    suspend fun getHiddenPosts(
        @Header("Authorization") token: String,
        @Path("batch") batch: Int
    ): Response<List<HiddenPost>>

    @GET("appeals/hidden/comments/{batch}/")
    suspend fun getHiddenComments(
        @Header("Authorization") token: String,
        @Path("batch") batch: Int
    ): Response<List<HiddenComment>>

    @GET("appeals/mine/{batch}/")
    suspend fun getMyAppeals(
        @Header("Authorization") token: String,
        @Path("batch") batch: Int
    ): Response<List<MyAppeal>>

    @POST("appeals/submit/")
    suspend fun submitAppeal(
        @Header("Authorization") token: String,
        @Body request: SubmitAppealRequest
    ): Response<SubmitAppealResponse>
}