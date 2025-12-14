package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.model.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.ResponseBody.Companion.toResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.POST
import java.time.LocalDate
import java.time.Period
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.util.UUID
import kotlin.random.Random

/**
 * A Stateful Stub that mimics the Django backend logic entirely in memory.
 * Useful for UI testing, Previews, or Offline/Demo modes.
 */
class StatefulStubbedAPI : PositiveOnlySocialAPI {

    // ============================================================================================
    // INTERNAL STORAGE (The "Database")
    // ============================================================================================

    private val users = mutableListOf<UserMock>()
    private val sessions = mutableListOf<SessionMock>()
    private val loginCookies = mutableListOf<LoginCookieMock>()
    private val posts = mutableListOf<PostMock>()
    private val commentThreads = mutableListOf<CommentThreadMock>()

    // Simulates the "Authorization: Bearer <token>" header.
    // Set this variable before making authenticated calls.
    var simulatedAuthToken: String? = null

    // Constants from backend
    private val POST_BATCH_SIZE = 10
    private val COMMENT_BATCH_SIZE = 10
    private val MAX_BEFORE_HIDING_POST = 5

    // ============================================================================================
    // MOCK DATA MODELS (Mirroring Django Models)
    // ============================================================================================

    private data class UserMock(
        val id: String = UUID.randomUUID().toString(),
        val username: String,
        val email: String,
        var passwordHash: String, // Storing plain text for stub simplicity, or simple hash
        var resetId: Int = -1,
        val following: MutableList<String> = mutableListOf(), // List of User IDs
        val followers: MutableList<String> = mutableListOf(),
        var isVerified: Boolean = false,
        var isAdult: Boolean = false,
    )

    private data class SessionMock(
        val managementToken: String,
        val userId: String,
        val ip: String
    )

    private data class LoginCookieMock(
        val seriesIdentifier: String,
        var token: String,
        val userId: String
    )

    private data class PostMock(
        val postIdentifier: String = UUID.randomUUID().toString(),
        val authorId: String,
        val imageUrl: String,
        val caption: String,
        val creationTime: Long = System.currentTimeMillis(),
        var hidden: Boolean = false,
        val likes: MutableSet<String> = mutableSetOf(), // Set of User IDs
        val reports: MutableSet<String> = mutableSetOf() // Set of User IDs
    )

    private data class CommentThreadMock(
        val threadIdentifier: String = UUID.randomUUID().toString(),
        val postId: String,
        val comments: MutableList<CommentMock> = mutableListOf()
    )

    private data class CommentMock(
        val commentIdentifier: String = UUID.randomUUID().toString(),
        val authorId: String,
        val body: String,
        val creationTime: Long = System.currentTimeMillis(),
        var hidden: Boolean = false,
        val likes: MutableSet<String> = mutableSetOf(),
        val reports: MutableSet<String> = mutableSetOf()
    )

    // ============================================================================================
    // HELPER FUNCTIONS
    // ============================================================================================

    private fun error(code: Int, message: String): Response<GenericResponse> {
        val errorBody = "{\"error\": \"$message\"}".toResponseBody("application/json".toMediaTypeOrNull())
        return Response.error(code, errorBody)
    }

    private fun <T> errorGeneric(code: Int, message: String): Response<T> {
        val errorBody = "{\"error\": \"$message\"}".toResponseBody("application/json".toMediaTypeOrNull())
        return Response.error(code, errorBody)
    }

    private fun getAuthorizedUser(token: String? = null): UserMock? {
        val tokenToUse = token ?: simulatedAuthToken ?: return null
        val session = sessions.find { it.managementToken == tokenToUse } ?: return null
        return users.find { it.id == session.userId }
    }

    // Simple regex validators matching backend Patterns
    private fun isValidAlphaNumeric(s: String) = s.matches(Regex("^[a-zA-Z0-9]*$"))
    private fun isValidEmail(s: String) = android.util.Patterns.EMAIL_ADDRESS.matcher(s).matches()

    // ============================================================================================
    // API IMPLEMENTATION
    // ============================================================================================

    override suspend fun register(request: RegisterRequest): Response<AuthResponse> {
        if (users.any { it.username == request.username || it.email == request.email }) {
            return errorGeneric(404, "User already exists")
        }

        // Create User
        val newUser = UserMock(
            username = request.username,
            email = request.email,
            passwordHash = request.password // Stub: Plain text
        )
        users.add(newUser)

        // Create Session
        val sessionToken = UUID.randomUUID().toString()
        sessions.add(SessionMock(sessionToken, newUser.id, request.ip))

        // Handle Remember Me
        var seriesId: String? = null
        var cookieToken: String? = null
        if (request.rememberMe.toBoolean()) {
            seriesId = UUID.randomUUID().toString()
            cookieToken = UUID.randomUUID().toString()
            loginCookies.add(LoginCookieMock(seriesId, cookieToken, newUser.id))
        }

        return Response.success(AuthResponse(sessionToken, seriesId, cookieToken))
    }

    override suspend fun loginUser(request: LoginRequest): Response<AuthResponse> {
        val user = users.find { it.username == request.usernameOrEmail || it.email == request.usernameOrEmail }

        if (user == null || user.passwordHash != request.password) {
            return errorGeneric(404, "No user exists with that information or password incorrect")
        }

        val sessionToken = UUID.randomUUID().toString()
        sessions.add(SessionMock(sessionToken, user.id, request.ip))

        var seriesId: String? = null
        var cookieToken: String? = null

        // Note: Backend logic handles strings or booleans for remember_me.
        // Since DTO defines it as String, we convert.
        if (request.rememberMe.toBoolean()) {
            seriesId = UUID.randomUUID().toString()
            cookieToken = UUID.randomUUID().toString()
            loginCookies.add(LoginCookieMock(seriesId, cookieToken, user.id))
        }

        // Auto-set the token for convenience in this stateful stub
        simulatedAuthToken = sessionToken

        return Response.success(AuthResponse(sessionToken, seriesId, cookieToken))
    }

    override suspend fun loginUserWithRememberMe(request: TokenRefreshRequest): Response<TokenRefreshResponse> {
        val cookie = loginCookies.find { it.seriesIdentifier == request.seriesIdentifier }
            ?: return errorGeneric(404, "Series identifier does not exist")

        if (cookie.token != request.loginCookieToken) {
            return errorGeneric(404, "Login cookie token does not match")
        }

        // Rotate tokens
        val newCookieToken = UUID.randomUUID().toString()
        cookie.token = newCookieToken

        val newSessionToken = UUID.randomUUID().toString()
        // Look up user from the old session token provided in request
        val oldSession = sessions.find { it.managementToken == request.sessionToken }

        if (oldSession == null) {
            // Fallback: find user by cookie (The python code actually checks the user via session first)
            // Logic deviation handling: strict to python code, if session invalid, it errors.
            // But strictly, if the cookie is valid, we know the user.
            // We will stick to finding user via the cookie relation for the stub to work robustly.
            val user = users.find { it.id == cookie.userId }!!
            sessions.add(SessionMock(newSessionToken, user.id, request.ip))
        } else {
            val user = users.find { it.id == oldSession.userId }!!
            sessions.add(SessionMock(newSessionToken, user.id, request.ip))
        }

        simulatedAuthToken = newSessionToken

        return Response.success(TokenRefreshResponse(newCookieToken, newSessionToken))
    }

    override suspend fun logout(token: String): Response<GenericResponse> {
        val user = getAuthorizedUser(token) ?: return error(401, "Invalid session")
        // Delete specific session
        sessions.removeIf { it.managementToken == token }
        return Response.success(GenericResponse("Logout successful", null))
    }

    override suspend fun deleteUser(token: String): Response<GenericResponse> {
        val user = getAuthorizedUser(token) ?: return error(401, "Invalid session")

        // Cascade delete
        posts.removeIf { it.authorId == user.id }
        sessions.removeIf { it.userId == user.id }
        loginCookies.removeIf { it.userId == user.id }
        users.remove(user)

        return Response.success(GenericResponse("User deleted successfully", null))
    }

    override suspend fun verifyIdentity(token: String, request: IdentityVerificationRequest): Response<GenericResponse> {
        // 1. Authenticate User
        // We reuse your existing helper to find the user via the session token
        val user = getAuthorizedUser(token) ?: return error(401, "Unauthorized")

        // 2. Parse Date
        // Using java.time (Standard for Android API 26+)
        val formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd")
        val birthDate: LocalDate = try {
            LocalDate.parse(request.dateOfBirth, formatter)
        } catch (e: DateTimeParseException) {
            return error(400, "Invalid Date Format. Please use yyyy-MM-dd")
        }

        // 3. Calculate Age
        // Period.between handles leap years and calendar math automatically
        val today = LocalDate.now()
        val age = Period.between(birthDate, today).years

        // 4. Update State
        // We modify the user object currently held in the 'users' mutable list
        user.isAdult = age >= 18
        user.isVerified = true

        return Response.success(GenericResponse("Identity verified successfully", null))
    }

    // ============================================================================================
    // PASSWORD RESET

    override suspend fun requestReset(request: ResetRequest): Response<GenericResponse> {
        // 1. Check if the provided string matches EITHER the email OR the username
        val user = users.find { it.email == request.usernameOrEmail || it.username == request.usernameOrEmail }

        if (user != null) {
            // 2. Assign a STATIC reset ID for testing purposes
            user.resetId = 123456

            return Response.success(GenericResponse("Password reset code generated", null))
        }

        return error(404, "No user found with that username or email")
    }

    override suspend fun verifyReset(usernameOrEmail: String, resetId: Int): Response<GenericResponse> {
        val user = users.find { it.username == usernameOrEmail || it.email == usernameOrEmail }
        if (user != null && user.resetId == resetId && user.resetId != -1) {
            user.resetId = -1 // Invalidate
            return Response.success(GenericResponse("Verification successful", null))
        }
        return error(404, "That reset id does not match")
    }

    override suspend fun resetPassword(request: PasswordResetSubmitRequest): Response<GenericResponse> {
        val user = users.find { it.username == request.username && it.email == request.email }
        if (user != null) {
            user.passwordHash = request.password
            return Response.success(GenericResponse("Password reset successfully", null))
        }
        return error(404, "No user with that username or email")
    }

    // ============================================================================================
    // POSTS
    // ============================================================================================

    override suspend fun makePost(token: String, request: CreatePostRequest): Response<CreatePostResponse> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")

        // Stub "Positivity" Check
        if (request.caption.contains("negative")) {
            return errorGeneric(404, "Text is not positive")
        }

        val newPost = PostMock(
            authorId = user.id,
            imageUrl = request.imageUrl,
            caption = request.caption
        )
        posts.add(newPost)
        return Response.success(CreatePostResponse(newPost.postIdentifier))
    }

    override suspend fun deletePost(token: String, postId: String): Response<GenericResponse> {
        val user = getAuthorizedUser(token) ?: return error(401, "Unauthorized")
        val post = posts.find { it.postIdentifier == postId }
            ?: return error(404, "No post with that identifier")

        if (post.authorId != user.id) {
            return error(404, "No post with that identifier by that user") // Mimic backend error msg
        }

        posts.remove(post)
        return Response.success(GenericResponse("Post deleted", null))
    }

    override suspend fun reportPost(token: String, postId: String, request: ReportRequest): Response<GenericResponse> {
        val user = getAuthorizedUser(token) ?: return error(401, "Unauthorized")
        val post = posts.find { it.postIdentifier == postId }
            ?: return error(404, "No post with that identifier")

        if (post.authorId == user.id) return error(404, "Cannot report own post")
        if (post.reports.contains(user.id)) return error(404, "Cannot report post twice")

        post.reports.add(user.id)
        if (post.reports.size > MAX_BEFORE_HIDING_POST) {
            post.hidden = true
        }
        return Response.success(GenericResponse("Post reported", null))
    }

    override suspend fun likePost(token: String, postId: String): Response<GenericResponse> {
        val user = getAuthorizedUser(token) ?: return error(401, "Unauthorized")
        val post = posts.find { it.postIdentifier == postId }
            ?: return error(404, "No post with that identifier")

        if (post.authorId == user.id) return error(404, "Cannot like own post")
        if (post.likes.contains(user.id)) return error(404, "Already liked post")

        post.likes.add(user.id)
        return Response.success(GenericResponse("Post liked", null))
    }

    override suspend fun unlikePost(token: String, postId: String): Response<GenericResponse> {
        val user = getAuthorizedUser(token) ?: return error(401, "Unauthorized")
        val post = posts.find { it.postIdentifier == postId } ?: return error(404, "No post")

        if (post.likes.contains(user.id)) {
            post.likes.remove(user.id)
            return Response.success(GenericResponse("Post unliked", null))
        }
        return error(404, "Post not liked yet")
    }

    // ============================================================================================
    // FEED / RETRIEVAL
    // ============================================================================================

    override suspend fun getPostsInFeed(token: String, batch: Int): Response<List<Post>> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")

        // Stub Feed Algorithm: Just return all posts not hidden, reverse chrono
        val allPosts = posts.filter { !it.hidden }.sortedByDescending { it.creationTime }
        val batched = getBatch(allPosts, batch, POST_BATCH_SIZE)

        val dtos = batched.map { post ->
            val author = users.find { it.id == post.authorId }!!
            Post(post.postIdentifier, post.imageUrl, post.caption, authorUsername = author.username)
        }
        return Response.success(dtos)
    }

    override suspend fun getFollowedPosts(token: String, batch: Int): Response<List<Post>> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")

        val followedPosts = posts.filter { !it.hidden && user.following.contains(it.authorId) }
            .sortedByDescending { it.creationTime }

        val batched = getBatch(followedPosts, batch, POST_BATCH_SIZE)
        val dtos = batched.map { post ->
            val author = users.find { it.id == post.authorId }!!
            Post(post.postIdentifier, post.imageUrl, post.caption, authorUsername = author.username)
        }
        return Response.success(dtos)
    }

    override suspend fun getPostsForUser(token: String, username: String, batch: Int): Response<List<Post>> {
        val targetUser = users.find { it.username == username }
            ?: return errorGeneric(404, "User not found")

        val userPosts = posts.filter { !it.hidden && it.authorId == targetUser.id }
            .sortedByDescending { it.creationTime }

        val batched = getBatch(userPosts, batch, POST_BATCH_SIZE)
        val dtos = batched.map { post ->
            Post(post.postIdentifier, post.imageUrl, post.caption, authorUsername = targetUser.username)
        }
        return Response.success(dtos)
    }

    override suspend fun getPostDetails(postId: String): Response<Post> {
        val post = posts.find { it.postIdentifier == postId }
            ?: return errorGeneric(404, "No post with that identifier")
        val author = users.find { it.id == post.authorId }!!

        return Response.success(Post(
            post.postIdentifier,
            post.imageUrl,
            post.caption,
            authorUsername = author.username,
            post.likes.count()
        ))
    }

    // ============================================================================================
    // COMMENTS
    // ============================================================================================

    override suspend fun commentOnPost(token: String, postId: String, request: CommentRequest): Response<CommentResponse> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        if (!posts.any { it.postIdentifier == postId }) return errorGeneric(404, "Post not found")

        // Create Thread
        val thread = CommentThreadMock(postId = postId)
        commentThreads.add(thread)

        // Create Comment
        val comment = CommentMock(authorId = user.id, body = request.commentText)
        thread.comments.add(comment)

        return Response.success(CommentResponse(thread.threadIdentifier, comment.commentIdentifier))
    }

    override suspend fun replyToThread(token: String, postId: String, threadId: String, request: CommentRequest): Response<CommentResponse> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        val thread = commentThreads.find { it.threadIdentifier == threadId && it.postId == postId }
            ?: return errorGeneric(404, "Thread not found")

        val comment = CommentMock(authorId = user.id, body = request.commentText)
        thread.comments.add(comment)

        return Response.success(CommentResponse(null, comment.commentIdentifier))
    }

    override suspend fun likeComment(token: String, postId: String, threadId: String, commentId: String): Response<GenericResponse> {
        val user = getAuthorizedUser(token) ?: return error(401, "Unauthorized")
        val comment = findComment(postId, threadId, commentId) ?: return error(404, "Comment not found")

        if (comment.authorId == user.id) return error(404, "Cannot like own comment")
        if (comment.likes.contains(user.id)) return error(404, "Already liked comment")

        comment.likes.add(user.id)
        return Response.success(GenericResponse("Comment liked", null))
    }

    override suspend fun unlikeComment(token: String, postId: String, threadId: String, commentId: String): Response<GenericResponse> {
        val user = getAuthorizedUser(token) ?: return error(401, "Unauthorized")
        val comment = findComment(postId, threadId, commentId) ?: return error(404, "Comment not found")

        if (comment.likes.contains(user.id)) {
            comment.likes.remove(user.id)
            return Response.success(GenericResponse("Comment unliked", null))
        }
        return error(404, "Comment not liked yet")
    }

    override suspend fun deleteComment(token: String, postId: String, threadId: String, commentId: String): Response<GenericResponse> {
        val user = getAuthorizedUser(token) ?: return error(401, "Unauthorized")
        val thread = commentThreads.find { it.threadIdentifier == threadId } ?: return error(404, "Thread not found")
        val comment = thread.comments.find { it.commentIdentifier == commentId } ?: return error(404, "Comment not found")

        if (comment.authorId != user.id) return error(404, "Not authorized")

        thread.comments.remove(comment)
        return Response.success(GenericResponse("Comment deleted", null))
    }

    override suspend fun reportComment(token: String, postId: String, threadId: String, commentId: String, request: ReportRequest): Response<GenericResponse> {
        val user = getAuthorizedUser(token) ?: return error(401, "Unauthorized")
        val comment = findComment(postId, threadId, commentId) ?: return error(404, "Comment not found")

        if (comment.authorId == user.id) return error(404, "Cannot report own comment")
        if (comment.reports.contains(user.id)) return error(404, "Already reported")

        comment.reports.add(user.id)
        if (comment.reports.size > 5) comment.hidden = true // Stub limit

        return Response.success(GenericResponse("Comment reported", null))
    }

    override suspend fun getCommentsForPost(postId: String, batch: Int): Response<List<CommentThreadDto>> {
        val threads = commentThreads.filter { it.postId == postId }
        val batched = getBatch(threads, batch, COMMENT_BATCH_SIZE)
        return Response.success(batched.map { CommentThreadDto(it.threadIdentifier) })
    }

    override suspend fun getCommentsForThread(threadId: String, batch: Int): Response<List<CommentDto>> {
        val thread = commentThreads.find { it.threadIdentifier == threadId }
            ?: return errorGeneric(404, "Thread not found")

        val comments = thread.comments.filter { !it.hidden }.sortedBy { it.creationTime }
        val batched = getBatch(comments, batch, COMMENT_BATCH_SIZE)

        val dtos = batched.map { c ->
            val author = users.find { it.id == c.authorId }!!
            CommentDto(
                c.commentIdentifier,
                c.body,
                author.username,
                c.creationTime.toString(),
                c.creationTime.toString(),
                c.likes.size
            )
        }
        return Response.success(dtos)
    }

    // ============================================================================================
    // USER / PROFILE
    // ============================================================================================

    override suspend fun searchUsers(token: String, fragment: String): Response<List<User>> {
        val currentUser = getAuthorizedUser(token)
        val matches = users
            .filter { it.username.contains(fragment, ignoreCase = true) && it.id != currentUser?.id }
            .take(10)
            .map { User(it.username, it.isVerified) }
        return Response.success(matches)
    }

    override suspend fun followUser(token: String, username: String): Response<GenericResponse> {
        val user = getAuthorizedUser(token) ?: return error(401, "Unauthorized")
        val target = users.find { it.username == username } ?: return error(404, "User not found")

        if (user.id == target.id) return error(404, "Cannot follow self")
        if (user.following.contains(target.id)) return error(404, "Already following")

        user.following.add(target.id)
        target.followers.add(user.id)
        return Response.success(GenericResponse("User followed", null))
    }

    override suspend fun unfollowUser(token: String, username: String): Response<GenericResponse> {
        val user = getAuthorizedUser(token) ?: return error(401, "Unauthorized")
        val target = users.find { it.username == username } ?: return error(404, "User not found")

        if (!user.following.contains(target.id)) return error(404, "Not following")

        user.following.remove(target.id)
        target.followers.remove(user.id)
        return Response.success(GenericResponse("User unfollowed", null))
    }

    override suspend fun getProfileDetails(token: String, username: String): Response<ProfileDetailsResponse> {
        val user = getAuthorizedUser(token) // Can be null if public profile view? Python code required login.
        val target = users.find { it.username == username } ?: return errorGeneric(404, "User not found")

        val postCount = posts.count { it.authorId == target.id }
        val isFollowing = user?.following?.contains(target.id) ?: false

        return Response.success(ProfileDetailsResponse(
            target.username,
            postCount,
            target.followers.size,
            target.following.size,
            isFollowing
        ))
    }

    // ============================================================================================
    // UTILS
    // ============================================================================================

    private fun <T> getBatch(list: List<T>, batchIndex: Int, batchSize: Int): List<T> {
        val start = batchIndex * batchSize
        if (start >= list.size) return emptyList()
        val end = (start + batchSize).coerceAtMost(list.size)
        return list.subList(start, end)
    }

    private fun findComment(postId: String, threadId: String, commentId: String): CommentMock? {
        val thread = commentThreads.find { it.threadIdentifier == threadId && it.postId == postId } ?: return null
        return thread.comments.find { it.commentIdentifier == commentId }
    }
}