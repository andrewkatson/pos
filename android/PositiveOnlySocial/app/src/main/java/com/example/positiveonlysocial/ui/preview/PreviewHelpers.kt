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
    override suspend fun loginUser(request: LoginRequest): Response<AuthResponse> {
        return Response.success(
            AuthResponse(
                sessionToken = "mock_session_token",
                seriesIdentifier = "mock_series_id",
                loginCookieToken = "mock_login_cookie"
            )
        )
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

    override suspend fun verifyReset(
        usernameOrEmail: String,
        resetId: Int
    ): Response<GenericResponse> {
        return Response.success(
            GenericResponse(
                message = "Reset verified",
                error = null
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

    override suspend fun getPostDetails(postId: String): Response<Post> {
        return Response.success(
            Post(
                postIdentifier = postId,
                imageUrl = "https://example.com/detail.jpg",
                caption = "Detailed view of the post",
                authorUsername = "mock_author",
                likeCount = 100
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

    override suspend fun getCommentsForPost(
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
                    likeCount = 5
                ),
                CommentDto(
                    commentIdentifier = "c2",
                    body = "I agree!",
                    authorUsername = "fan_2",
                    creationTime = "2023-01-01T12:05:00Z",
                    updatedTime = "2023-01-01T12:05:00Z",
                    likeCount = 2
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
}

object PreviewHelpers {
    val mockKeychainHelper = MockKeychainHelper()
    val mockApi = MockPositiveOnlySocialAPI()
    val mockAuthManager = AuthenticationManager(mockKeychainHelper)
}
