package com.example.positiveonlysocial.ui.preview

import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.model.*
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import retrofit2.Response

class MockKeychainHelper : KeychainHelperProtocol {
    private val storage = mutableMapOf<String, Any>()

    override fun <T> save(value: T, service: String, account: String) {
        storage["$service:$account"] = value as Any
    }

    override fun <T> load(type: Class<T>, service: String, account: String): T? {
        return storage["$service:$account"] as? T
    }

    override fun delete(service: String, account: String) {
        storage.remove("$service:$account")
    }
}

class MockPositiveOnlySocialAPI : PositiveOnlySocialAPI {
    override suspend fun loginUser(request: LoginRequest): Response<LoginResponse> {
        return Response.success(
            LoginResponse(
                sessionToken = "mock_session_token",
                username = request.usernameOrEmail,
                userId = "00000000-0000-0000-0000-000000000001",
                seriesIdentifier = "mock_series_id",
                loginCookieToken = "mock_login_cookie"
            )
        )
    }

    // --- Two-Factor Authentication (issue #348) ---

    override suspend fun loginUser2FA(request: LoginTwoFactorRequest): Response<AuthResponse> {
        return Response.success(
            AuthResponse(
                sessionToken = "mock_session_token",
                username = "mock_user",
                userId = "00000000-0000-0000-0000-000000000001",
                seriesIdentifier = "mock_series_id",
                loginCookieToken = "mock_login_cookie"
            )
        )
    }

    override suspend fun setupTotp(token: String): Response<TotpSetupResponse> {
        return Response.success(
            TotpSetupResponse(
                totpSecret = "PREVIEWSECRETBASE32PREVIEWSECRET",
                otpauthUri = "otpauth://totp/Positive%20Only%20Social:preview@example.com?secret=PREVIEWSECRETBASE32PREVIEWSECRET&issuer=Positive%20Only%20Social"
            )
        )
    }

    override suspend fun confirmTotp(token: String, request: ConfirmTotpRequest): Response<ConfirmTotpResponse> {
        return Response.success(
            ConfirmTotpResponse(
                totpEnabled = true,
                recoveryCodes = (0 until 10).map { "recover${it}ab" }
            )
        )
    }

    override suspend fun disableTotp(token: String, request: DisableTotpRequest): Response<DisableTotpResponse> {
        return Response.success(DisableTotpResponse(totpEnabled = false))
    }

    override suspend fun loginUserWithRememberMe(request: TokenRefreshRequest): Response<TokenRefreshResponse> {
        return Response.success(
            TokenRefreshResponse(
                newLoginCookieToken = "new_mock_cookie",
                newSessionToken = "new_mock_session"
            )
        )
    }

    override suspend fun register(request: RegisterRequest): Response<AuthResponse> {
        return Response.success(
            AuthResponse(
                sessionToken = "mock_session_token",
                username = request.username,
                userId = "00000000-0000-0000-0000-000000000001",
                seriesIdentifier = "mock_series_id",
                loginCookieToken = "mock_login_cookie"
            )
        )
    }

    override suspend fun logout(token: String): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Logged out successfully",
                error = null
            )
        )
    }

    override suspend fun deleteUser(token: String): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "User deleted successfully",
                error = null
            )
        )
    }

    override suspend fun verifyIdentity(
        token: String,
        request: IdentityVerificationRequest
    ): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Identity verified successfully",
                error = null
            )
        )
    }

    override suspend fun requestReset(request: ResetRequest): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Reset email sent",
                error = null
            )
        )
    }

    override suspend fun verifyReset(request: VerificationRequest): Response<VerifyResetResponse> {
        return Response.success(
            VerifyResetResponse(
                message = "Reset verified",
                error = null,
                resetToken = "preview_stub_token"
            )
        )
    }

    override suspend fun resetPassword(request: PasswordResetSubmitRequest): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Password reset successfully",
                error = null
            )
        )
    }

    override suspend fun verifyEmail(request: VerifyEmailRequest): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Email verified",
                error = null
            )
        )
    }

    override suspend fun resendVerificationEmail(request: ResendVerificationEmailRequest): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Verification email sent",
                error = null
            )
        )
    }

    override suspend fun getPostsInFeed(token: String, batch: Int): Response<List<Post>> {
        return Response.success(
            listOf(
                Post(
                    postIdentifier = "1",
                    imageUrl = "https://example.com/image1.jpg",
                    caption = "Beautiful sunset!",
                    authorUsername = "nature_lover",
                    likeCount = 120
                ),
                Post(
                    postIdentifier = "2",
                    imageUrl = "https://example.com/image2.jpg",
                    caption = "My new puppy",
                    authorUsername = "dog_fan",
                    likeCount = 350
                ),
                // A text-only post (#307) so previews exercise the caption tile.
                Post(
                    postIdentifier = "5",
                    imageUrl = null,
                    caption = "Words only today — feeling grateful!",
                    authorUsername = "text_poster",
                    likeCount = 12
                )
            )
        )
    }

    override suspend fun getFollowedPosts(token: String, batch: Int): Response<List<Post>> {
        return Response.success(
            listOf(
                Post(
                    postIdentifier = "3",
                    imageUrl = "https://example.com/image3.jpg",
                    caption = "Coffee time",
                    authorUsername = "coffee_addict",
                    likeCount = 45
                )
            )
        )
    }

    override suspend fun getPostsForUser(
        token: String,
        username: String,
        batch: Int
    ): Response<List<Post>> {
        return Response.success(
            listOf(
                Post(
                    postIdentifier = "4",
                    imageUrl = "https://example.com/user_post.jpg",
                    caption = "Just me",
                    authorUsername = username,
                    likeCount = 10
                )
            )
        )
    }

    override suspend fun getPostDetails(token: String, postId: String): Response<Post> {
        return Response.success(
            Post(
                postIdentifier = postId,
                imageUrl = "https://example.com/detail.jpg",
                caption = "Detailed view of the post",
                authorUsername = "mock_author",
                likeCount = 100,
                isLiked = false
            )
        )
    }

    override suspend fun createUploadUrl(token: String): Response<CreateUploadUrlResponse> {
        return Response.success(
            CreateUploadUrlResponse(
                uploadUrl = "https://example-bucket.s3.us-east-2.amazonaws.com/mock-user/mock-image.jpeg?X-Amz-Signature=mock",
                imageUrl = "https://example-bucket.s3.us-east-2.amazonaws.com/mock-user/mock-image.jpeg"
            )
        )
    }

    override suspend fun makePost(
        token: String,
        request: CreatePostRequest
    ): Response<CreatePostResponse> {
        return Response.success(
            CreatePostResponse(
                postIdentifier = "new_post_id_123"
            )
        )
    }

    override suspend fun getPostStatus(token: String, postId: String): Response<PostStatusResponse> {
        // Previews treat every post as already approved (issue #282).
        return Response.success(
            PostStatusResponse(
                postIdentifier = postId,
                status = "approved"
            )
        )
    }

    override suspend fun deletePost(token: String, postId: String): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Post deleted",
                error = null
            )
        )
    }

    override suspend fun reportPost(
        token: String,
        postId: String,
        request: ReportRequest
    ): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Post reported",
                error = null
            )
        )
    }

    override suspend fun retractReportPost(
        token: String,
        postId: String
    ): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Post report retracted",
                error = null
            )
        )
    }

    override suspend fun likePost(token: String, postId: String): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Post liked",
                error = null
            )
        )
    }

    override suspend fun unlikePost(token: String, postId: String): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Post unliked",
                error = null
            )
        )
    }

    override suspend fun commentOnPost(
        token: String,
        postId: String,
        request: CommentRequest
    ): Response<CommentResponse> {
        return Response.success(
            CommentResponse(
                threadIdentifier = "thread_1",
                commentIdentifier = "comment_new"
            )
        )
    }

    override suspend fun replyToThread(
        token: String,
        postId: String,
        threadId: String,
        request: CommentRequest
    ): Response<CommentResponse> {
        return Response.success(
            CommentResponse(
                threadIdentifier = threadId,
                commentIdentifier = "reply_new"
            )
        )
    }

    override suspend fun likeComment(
        token: String,
        postId: String,
        threadId: String,
        commentId: String
    ): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Comment liked",
                error = null
            )
        )
    }

    override suspend fun unlikeComment(
        token: String,
        postId: String,
        threadId: String,
        commentId: String
    ): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Comment unliked",
                error = null
            )
        )
    }

    override suspend fun deleteComment(
        token: String,
        postId: String,
        threadId: String,
        commentId: String
    ): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Comment deleted",
                error = null
            )
        )
    }

    override suspend fun reportComment(
        token: String,
        postId: String,
        threadId: String,
        commentId: String,
        request: ReportRequest
    ): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Comment reported",
                error = null
            )
        )
    }

    override suspend fun retractReportComment(
        token: String,
        postId: String,
        threadId: String,
        commentId: String
    ): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Comment report retracted",
                error = null
            )
        )
    }

    override suspend fun getCommentsForPost(
        token: String,
        postId: String,
        batch: Int
    ): Response<List<CommentThreadDto>> {
        return Response.success(
            listOf(
                CommentThreadDto(threadIdentifier = "thread_1"),
                CommentThreadDto(threadIdentifier = "thread_2")
            )
        )
    }

    override suspend fun getCommentsForThread(
        token: String,
        threadId: String,
        batch: Int
    ): Response<List<CommentDto>> {
        return Response.success(
            listOf(
                CommentDto(
                    commentIdentifier = "c1",
                    body = "Great post!",
                    authorUsername = "fan_1",
                    creationTime = "2023-01-01T12:00:00Z",
                    updatedTime = "2023-01-01T12:00:00Z",
                    likeCount = 5,
                    isLiked = false
                ),
                CommentDto(
                    commentIdentifier = "c2",
                    body = "I agree!",
                    authorUsername = "fan_2",
                    creationTime = "2023-01-01T12:05:00Z",
                    updatedTime = "2023-01-01T12:05:00Z",
                    likeCount = 2,
                    isLiked = true
                )
            )
        )
    }

    override suspend fun searchUsers(
        token: String,
        fragment: String
    ): Response<List<User>> {
        return Response.success(
            listOf(
                User(username = "search_result_1", identityIsVerified = true),
                User(username = "search_result_2", identityIsVerified = false)
            )
        )
    }

    override suspend fun followUser(
        token: String,
        username: String
    ): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Followed user",
                error = null
            )
        )
    }

    override suspend fun unfollowUser(
        token: String,
        username: String
    ): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Unfollowed user",
                error = null
            )
        )
    }

    override suspend fun toggleBlock(
        token: String,
        username: String
    ): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "User blocked/unblocked",
                error = null
            )
        )
    }

    override suspend fun getBlockedUsers(
        token: String
    ): Response<List<User>> {
        return Response.success(
            listOf(
                User(username = "blocked_user_1", identityIsVerified = true),
                User(username = "blocked_user_2", identityIsVerified = false)
            )
        )
    }

    override suspend fun getProfileDetails(
        token: String,
        username: String
    ): Response<ProfileDetailsResponse> {
        return Response.success(
            ProfileDetailsResponse(
                username = username,
                postCount = 10,
                followerCount = 100,
                followingCount = 50,
                isFollowing = false
            )
        )
    }

    override suspend fun getHiddenPosts(token: String, batch: Int): Response<List<HiddenPost>> =
        Response.success(emptyList())

    override suspend fun getHiddenComments(token: String, batch: Int): Response<List<HiddenComment>> =
        Response.success(emptyList())

    override suspend fun getMyAppeals(token: String, batch: Int): Response<List<MyAppeal>> =
        Response.success(emptyList())

    override suspend fun submitAppeal(token: String, request: SubmitAppealRequest): Response<SubmitAppealResponse> =
        Response.success(SubmitAppealResponse("preview-appeal"))
}

object PreviewHelpers {
    val mockKeychainHelper = MockKeychainHelper()
    val mockApi = MockPositiveOnlySocialAPI()
    val mockAuthManager = AuthenticationManager(mockKeychainHelper)
}
