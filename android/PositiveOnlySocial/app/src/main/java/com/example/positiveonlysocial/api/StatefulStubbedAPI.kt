package com.example.positiveonlysocial.api

import com.example.positiveonlysocial.data.constants.Constants
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

    companion object {
        // The stub has no clock-based TOTP; this fixed code is the one the
        // stub accepts, mirroring the fixed codes in the website/iOS stubs.
        const val STUB_TOTP_CODE = "123456"

        // Used for the credential-shaped stub values (TOTP secret), where
        // Kotlin's Random.Default would be an insecure generator.
        private val secureRandom = java.security.SecureRandom()
    }

    // ============================================================================================
    // INTERNAL STORAGE (The "Database")
    // ============================================================================================

    private val users = mutableListOf<UserMock>()
    private val sessions = mutableListOf<SessionMock>()
    private val loginCookies = mutableListOf<LoginCookieMock>()
    private val twoFactorChallenges = mutableListOf<TwoFactorChallengeMock>()
    private val posts = mutableListOf<PostMock>()
    private val commentThreads = mutableListOf<CommentThreadMock>()
    private val appeals = mutableListOf<AppealMock>()

    // Monotonic source for membership numbers (issue #198). A dedicated counter
    // rather than users.size so a delete + re-register never reuses a number,
    // matching the backend's "creation order, never reused" behavior.
    private var membershipCounter = 0

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
        var verificationToken: String? = null,
        var resetToken: String? = null,
        // The real backend starts accounts unverified and gates everything on
        // the emailed link; the stub has no inbox, so accounts start verified
        // to keep offline/demo mode usable.
        var emailVerified: Boolean = true,
        var emailVerificationToken: String? = null,
        val following: MutableList<String> = mutableListOf(), // List of User IDs
        val followers: MutableList<String> = mutableListOf(),
        var isVerified: Boolean = false,
        var isAdult: Boolean = false,
        // Sequential join number (issue #198), assigned in registration order.
        var membershipNumber: Int? = null,
        val blocked: MutableList<String> = mutableListOf(),
        val blockedBy: MutableList<String> = mutableListOf(),
        // Two-factor authentication (issue #348). A secret without the enabled
        // flag is a pending enrollment; recovery codes are removed as used.
        var totpSecret: String? = null,
        var totpEnabled: Boolean = false,
        val recoveryCodes: MutableList<String> = mutableListOf(),
        // Profile photo (issue #7). Only the approved photo is ever exposed to
        // others; the pending upload is the owner's immediate preview. Status is
        // one of "none"|"pending"|"approved"|"rejected".
        var profileImageUrl: String? = null,
        var pendingProfileImageUrl: String? = null,
        var profileImageStatus: String = "none",
        var profileImageReasonCode: String? = null
    )

    // A pending two-factor login, issued by loginUser when the account has
    // TOTP enabled and consumed by loginUser2FA.
    private data class TwoFactorChallengeMock(
        val challengeToken: String,
        val userId: String,
        val rememberMe: Boolean,
        val ip: String
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
        // Null for a text-only post (#307).
        val imageUrl: String?,
        val caption: String,
        // Whole-caption font + whole-tile background color keys (issue #318).
        val captionFont: String = "default",
        val backgroundColor: String = "default",
        val creationTime: Long = System.currentTimeMillis(),
        var hidden: Boolean = false,
        var hiddenReason: String = "",
        // Public reason code recorded by the (stubbed) async classifier (#282).
        var reasonCode: String? = null,
        val likes: MutableSet<String> = mutableSetOf(), // Set of User IDs
        // Reporting user id -> their reason, so retract flows can show the reason.
        val reports: MutableMap<String, String> = mutableMapOf()
    )

    private data class AppealMock(
        val appealIdentifier: String = UUID.randomUUID().toString(),
        val appellantId: String,
        val targetType: String, // "post" or "comment"
        val targetId: String,
        val reason: String,
        val contentSnapshot: String,
        val status: String = "pending"
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
        // Inline formatting spans over `body` (issue #318); null = plain.
        val bodyFormatting: List<CommentFormatSpan>? = null,
        val creationTime: Long = System.currentTimeMillis(),
        var hidden: Boolean = false,
        var hiddenReason: String = "",
        val likes: MutableSet<String> = mutableSetOf(),
        // Reporting user id -> their reason, so retract flows can show the reason.
        val reports: MutableMap<String, String> = mutableMapOf()
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

        // Create User. Assign the next sequential membership number (issue
        // #198), mirroring the backend which numbers accounts in creation order
        // and never reuses a number even after a delete.
        val newUser = UserMock(
            username = request.username,
            email = request.email,
            passwordHash = request.password, // Stub: Plain text
            membershipNumber = ++membershipCounter
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

        return Response.success(AuthResponse(sessionToken, newUser.username, newUser.id, seriesId, cookieToken, newUser.membershipNumber))
    }

    override suspend fun loginUser(request: LoginRequest): Response<LoginResponse> {
        val user = users.find { it.username == request.usernameOrEmail || it.email == request.usernameOrEmail }

        if (user == null || user.passwordHash != request.password) {
            return errorGeneric(404, "No user exists with that information or password incorrect")
        }

        // 2FA-enrolled accounts get a challenge instead of a session, mirroring
        // login_user in backend/user_system/views.py.
        if (user.totpEnabled) {
            // Only one challenge is ever live per user, matching login_user in
            // the backend — otherwise the per-challenge attempt limit could be
            // multiplied, and the list would grow unbounded across retries.
            twoFactorChallenges.removeIf { it.userId == user.id }
            val challenge = TwoFactorChallengeMock(
                challengeToken = UUID.randomUUID().toString(),
                userId = user.id,
                rememberMe = request.rememberMe.toBoolean(),
                ip = request.ip
            )
            twoFactorChallenges.add(challenge)
            return Response.success(
                LoginResponse(twoFactorRequired = true, challengeToken = challenge.challengeToken)
            )
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

        return Response.success(
            LoginResponse(
                sessionToken = sessionToken,
                username = user.username,
                userId = user.id,
                seriesIdentifier = seriesId,
                loginCookieToken = cookieToken
            )
        )
    }

    override suspend fun loginUser2FA(request: LoginTwoFactorRequest): Response<AuthResponse> {
        val challenge = twoFactorChallenges.find { it.challengeToken == request.challengeToken }
            ?: return errorGeneric(400, Constants.INVALID_TWO_FACTOR_CHALLENGE)
        val user = users.find { it.id == challenge.userId }
            ?: return errorGeneric(400, Constants.INVALID_TWO_FACTOR_CHALLENGE)

        val totpCode = request.totpCode
        val recoveryCode = request.recoveryCode
        val codeOk = when {
            totpCode != null && recoveryCode == null -> totpCode == STUB_TOTP_CODE
            // Recovery codes are single-use: consume on success.
            recoveryCode != null && totpCode == null -> user.recoveryCodes.remove(recoveryCode)
            else -> return errorGeneric(400, "Invalid fields ['TOTP_CODE', 'RECOVERY_CODE']")
        }
        if (!codeOk) {
            return errorGeneric(400, "Invalid two-factor code")
        }

        twoFactorChallenges.remove(challenge)

        val sessionToken = UUID.randomUUID().toString()
        sessions.add(SessionMock(sessionToken, user.id, challenge.ip))
        simulatedAuthToken = sessionToken

        var seriesId: String? = null
        var cookieToken: String? = null
        if (challenge.rememberMe) {
            seriesId = UUID.randomUUID().toString()
            cookieToken = UUID.randomUUID().toString()
            loginCookies.add(LoginCookieMock(seriesId, cookieToken, user.id))
        }

        return Response.success(AuthResponse(sessionToken, user.username, user.id, seriesId, cookieToken))
    }

    override suspend fun setupTotp(token: String): Response<TotpSetupResponse> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Invalid session")
        if (user.totpEnabled) {
            return errorGeneric(400, "Two-factor authentication is already enabled")
        }
        // Re-running setup before confirming simply replaces the pending secret.
        // Use the RFC 4648 Base32 alphabet (A-Z, 2-7) so the otpauth:// URI is a
        // valid TOTP secret that real authenticator apps and QR parsers accept.
        // The alphabet is exactly 32 characters, so indexing by a secure random
        // int over its length is unbiased. Kotlin's Random.Default is not
        // cryptographically secure, and this value is credential-shaped.
        val base32Alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        val secret = (1..32).map { base32Alphabet[secureRandom.nextInt(base32Alphabet.length)] }.joinToString("")
        user.totpSecret = secret
        return Response.success(
            TotpSetupResponse(
                totpSecret = secret,
                otpauthUri = "otpauth://totp/Positive%20Only%20Social:${user.email}?secret=$secret&issuer=Positive%20Only%20Social"
            )
        )
    }

    override suspend fun confirmTotp(token: String, request: ConfirmTotpRequest): Response<ConfirmTotpResponse> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Invalid session")
        if (user.totpEnabled) {
            return errorGeneric(400, "Two-factor authentication is already enabled")
        }
        if (user.totpSecret == null) {
            return errorGeneric(400, "Two-factor setup has not been started")
        }
        if (user.passwordHash != request.password) {
            return errorGeneric(400, "Invalid password")
        }
        if (request.totpCode != STUB_TOTP_CODE) {
            return errorGeneric(400, "Invalid two-factor code")
        }
        user.totpEnabled = true
        user.recoveryCodes.clear()
        repeat(10) {
            user.recoveryCodes.add(UUID.randomUUID().toString().replace("-", "").lowercase().take(10))
        }
        return Response.success(ConfirmTotpResponse(totpEnabled = true, recoveryCodes = user.recoveryCodes.toList()))
    }

    override suspend fun disableTotp(token: String, request: DisableTotpRequest): Response<DisableTotpResponse> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Invalid session")
        if (!user.totpEnabled) {
            return errorGeneric(400, "Two-factor authentication is not enabled")
        }
        if (user.passwordHash != request.password) {
            return errorGeneric(400, "Invalid password")
        }
        val totpCode = request.totpCode
        val recoveryCode = request.recoveryCode
        val codeOk = when {
            totpCode != null && recoveryCode == null -> totpCode == STUB_TOTP_CODE
            recoveryCode != null && totpCode == null -> user.recoveryCodes.remove(recoveryCode)
            else -> false
        }
        if (!codeOk) {
            return errorGeneric(400, "Invalid two-factor code")
        }
        user.totpSecret = null
        user.totpEnabled = false
        user.recoveryCodes.clear()
        twoFactorChallenges.removeIf { it.userId == user.id }
        return Response.success(DisableTotpResponse(totpEnabled = false))
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
            val stubToken = "stub_verification_token_${user.username}"
            user.verificationToken = stubToken
            return Response.success(GenericResponse("Password reset token generated", null))
        }

        return error(404, "No user found with that username or email")
    }

    override suspend fun verifyReset(request: VerificationRequest): Response<VerifyResetResponse> {
        val user = users.find { it.username == request.usernameOrEmail || it.email == request.usernameOrEmail }
        if (user != null && user.verificationToken != null && user.verificationToken == request.verificationToken) {
            val resetToken = "stub_reset_token_${user.username}"
            user.verificationToken = null
            user.resetToken = resetToken
            return Response.success(VerifyResetResponse("Verification successful", null, resetToken))
        }
        return errorGeneric(400, "Invalid or expired verification token")
    }

    override suspend fun resetPassword(request: PasswordResetSubmitRequest): Response<GenericResponse> {
        val user = users.find { it.username == request.username && it.email == request.email }
        if (user != null && user.resetToken != null && user.resetToken == request.resetToken) {
            user.passwordHash = request.password
            user.resetToken = null
            return Response.success(GenericResponse("Password reset successfully", null))
        }
        return error(400, "Invalid reset token or no user with that username or email")
    }

    // ============================================================================================
    // email verification
    // ============================================================================================

    override suspend fun verifyEmail(request: VerifyEmailRequest): Response<GenericResponse> {
        val user = users.find { it.emailVerificationToken != null && it.emailVerificationToken == request.verificationToken }
            ?: return errorGeneric(400, "Invalid or expired verification token")
        user.emailVerified = true
        user.emailVerificationToken = null
        return Response.success(GenericResponse("Email verified", null))
    }

    override suspend fun resendVerificationEmail(request: ResendVerificationEmailRequest): Response<GenericResponse> {
        val user = users.find { it.username == request.usernameOrEmail || it.email == request.usernameOrEmail }
            ?: return errorGeneric(400, "No user with that username or email")
        if (user.emailVerified) {
            return errorGeneric(400, "Email already verified")
        }
        user.emailVerificationToken = "stub_email_verification_token_${user.username}"
        return Response.success(GenericResponse("Verification email sent", null))
    }

    // ============================================================================================
    // posts
    // ============================================================================================

    override suspend fun createUploadUrl(token: String): Response<CreateUploadUrlResponse> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        // Mirror the backend: a fresh key under the user's prefix, returned as
        // both a "presigned" upload URL and the canonical image URL.
        val key = "${user.id}/stub-${java.util.UUID.randomUUID()}.jpeg"
        val imageUrl = "https://stub-bucket.s3.us-east-2.amazonaws.com/$key"
        return Response.success(
            CreateUploadUrlResponse(
                uploadUrl = "$imageUrl?X-Amz-Signature=stub",
                imageUrl = imageUrl
            )
        )
    }

    // When true, makePost leaves new posts in pending_classification until
    // resolvePendingClassifications() is called, so tests can exercise the
    // clients' reconcile path (#282).
    var deferClassification = false

    /** Plays the async worker's role for tests: classifies every post still pending (#282). */
    fun resolvePendingClassifications() {
        posts.filter { it.hiddenReason == "pending_classification" }.forEach { classify(it) }
    }

    // Stubbed async classifier (#282): a caption containing "borderline"
    // becomes an appealable rejection; everything else is approved.
    private fun classify(post: PostMock) {
        if (post.caption.contains("borderline")) {
            post.hidden = true
            post.hiddenReason = "classifier"
            post.reasonCode = "guidelines"
        } else {
            post.hidden = false
            post.hiddenReason = ""
        }
    }

    // Author-facing classification status, mirroring Post.classification_status.
    private fun classificationStatus(post: PostMock): String = when (post.hiddenReason) {
        "pending_classification" -> "pending"
        "classifier" -> "rejected"
        "classifier_final" -> "rejected_final"
        else -> "approved"
    }

    private fun isAppealable(post: PostMock): Boolean =
        post.hidden && post.hiddenReason != "pending_classification" && post.hiddenReason != "classifier_final"

    override suspend fun makePost(token: String, request: CreatePostRequest): Response<CreatePostResponse> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")

        // Stub pre-filter, mirroring the backend's cheap inline check (#282): a
        // blatant hit is rejected immediately and the post is never created.
        // 400, matching the real backend's validation/moderation rejection.
        if (request.caption.contains("negative")) {
            return errorGeneric(400, "Text is not positive")
        }

        val newPost = PostMock(
            authorId = user.id,
            imageUrl = request.imageUrl,
            caption = request.caption,
            captionFont = request.captionFont,
            backgroundColor = request.backgroundColor
        )
        newPost.hidden = true
        newPost.hiddenReason = "pending_classification"
        // The real backend classifies asynchronously in a worker; the stub
        // resolves instantly (like the backend's eager dev mode) but still
        // returns the pending response, so clients exercise the reconcile path.
        if (!deferClassification) {
            classify(newPost)
        }
        posts.add(newPost)
        return Response.success(
            CreatePostResponse(
                postIdentifier = newPost.postIdentifier,
                status = "pending",
                hidden = true,
                hiddenReason = "pending_classification",
                message = "Your post is being reviewed and will be visible to others once it is approved."
            )
        )
    }

    override suspend fun getPostStatus(token: String, postId: String): Response<PostStatusResponse> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        val post = posts.find { it.postIdentifier == postId && it.authorId == user.id }
            ?: return errorGeneric(400, "No post with that identifier by that user")
        val status = classificationStatus(post)
        val message = when (status) {
            "pending" -> "Your post is being reviewed and will be visible to others once it is approved."
            "rejected" -> "Your post did not pass automated review. It is hidden for now but you can appeal the decision."
            "rejected_final" -> "Your post did not pass automated review. This decision is final and cannot be appealed."
            else -> null
        }
        return Response.success(
            PostStatusResponse(
                postIdentifier = post.postIdentifier,
                status = status,
                reasonCode = post.reasonCode,
                appealable = isAppealable(post),
                hidden = post.hidden,
                hiddenReason = post.hiddenReason,
                message = message
            )
        )
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

        if (post.authorId == user.id) return error(400, "Cannot report own post")
        if (post.reports.contains(user.id)) return error(400, "Cannot report post twice")

        post.reports[user.id] = request.reason
        if (post.reports.size > MAX_BEFORE_HIDING_POST) {
            post.hidden = true
            post.hiddenReason = "reports"
        }
        return Response.success(GenericResponse("Post reported", null))
    }

    override suspend fun retractReportPost(token: String, postId: String): Response<GenericResponse> {
        val user = getAuthorizedUser(token) ?: return error(401, "Unauthorized")
        val post = posts.find { it.postIdentifier == postId }
            ?: return error(404, "No post with that identifier")

        if (!post.reports.contains(user.id)) return error(400, "Post not reported yet")

        post.reports.remove(user.id)
        // Un-hide only when reports were what hid it, mirroring the backend.
        if (post.hidden && post.hiddenReason == "reports" && post.reports.size <= MAX_BEFORE_HIDING_POST) {
            post.hidden = false
            post.hiddenReason = ""
        }
        return Response.success(GenericResponse("Post report retracted", null))
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
    // feed / retrieval
    // ============================================================================================

    override suspend fun getPostsInFeed(token: String, batch: Int): Response<List<Post>> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")

        val allPosts = posts.filter { 
            !it.hidden && 
            !user.blocked.contains(it.authorId) && 
            !user.blockedBy.contains(it.authorId)
        }.sortedByDescending { it.creationTime }
        val batched = getBatch(allPosts, batch, POST_BATCH_SIZE)

        val dtos = batched.map { post ->
            val author = users.find { it.id == post.authorId }!!
            listingDto(post, author.username, user.id)
        }
        return Response.success(dtos)
    }

    override suspend fun getFollowedPosts(token: String, batch: Int): Response<List<Post>> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")

        val followedPosts = posts.filter { 
            !it.hidden && 
            user.following.contains(it.authorId) &&
            !user.blocked.contains(it.authorId) &&
            !user.blockedBy.contains(it.authorId)
        }.sortedByDescending { it.creationTime }

        val batched = getBatch(followedPosts, batch, POST_BATCH_SIZE)
        val dtos = batched.map { post ->
            val author = users.find { it.id == post.authorId }!!
            listingDto(post, author.username, user.id)
        }
        return Response.success(dtos)
    }

    override suspend fun getPostsForUser(token: String, username: String, batch: Int): Response<List<Post>> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        val targetUser = users.find { it.username == username }
            ?: return errorGeneric(404, "User not found")

        if (user.blocked.contains(targetUser.id) || targetUser.blocked.contains(user.id)) {
            return Response.success(emptyList()) // Or error? returning empty list matches backend logic
        }

        // Mirrors the backend's visible_posts: authors see their own hidden
        // posts (pending, appealable, report-hidden) in their grid; everyone
        // else only sees live ones. Final-rejection tombstones are visible to
        // nobody (#282).
        val isOwnGrid = user.id == targetUser.id
        val userPosts = posts.filter { it.authorId == targetUser.id }
            .filter { it.hiddenReason != "classifier_final" }
            .filter { isOwnGrid || !it.hidden }
            .sortedByDescending { it.creationTime }

        val batched = getBatch(userPosts, batch, POST_BATCH_SIZE)
        val dtos = batched.map { post ->
            listingDto(post, targetUser.username, user.id, isOwnGrid)
        }
        return Response.success(dtos)
    }

    /**
     * The DTO the three post-listing endpoints return. Like the real backend,
     * they carry the same interaction state the post-details endpoint does —
     * likes, whether the viewer liked/reported it and their reason (issue #267) —
     * plus the comment count and creation time the feed rows show (issue #249).
     */
    private fun listingDto(
        post: PostMock,
        authorUsername: String,
        viewerId: String,
        isOwnGrid: Boolean = false
    ): Post {
        // The author's approved profile photo (issue #7): only an approved photo
        // is exposed, and the stub has no separate compressed bucket, so the
        // compressed and original URLs are the same.
        val avatar = approvedAvatarFor(post.authorId)
        return Post(
            post.postIdentifier,
            post.imageUrl,
            post.caption,
            captionFont = post.captionFont,
            backgroundColor = post.backgroundColor,
            authorUsername = authorUsername,
            likeCount = post.likes.count(),
            isLiked = post.likes.contains(viewerId),
            isReported = post.reports.contains(viewerId),
            reportReason = post.reports[viewerId],
            commentCount = visibleCommentCount(post.postIdentifier),
            creationTime = post.creationTime.toString(),
            // Author-only classification fields (#282), mirroring the backend:
            // only your own grid carries them. The feeds never do — others'
            // pending/hidden posts are filtered out before they get here.
            status = if (isOwnGrid) classificationStatus(post) else null,
            hidden = if (isOwnGrid) post.hidden else null,
            hiddenReason = if (isOwnGrid) post.hiddenReason else null,
            appealable = if (isOwnGrid) isAppealable(post) else null,
            authorProfileImageUrl = avatar,
            authorProfileImageOriginalUrl = avatar
        )
    }

    /** The author's approved profile photo URL, or null when they have none (#7). */
    private fun approvedAvatarFor(authorId: String): String? =
        users.find { it.id == authorId }
            ?.takeIf { it.profileImageStatus == "approved" }
            ?.profileImageUrl

    private fun visibleCommentCount(postIdentifier: String): Int =
        commentThreads
            .filter { it.postId == postIdentifier }
            .sumOf { thread -> thread.comments.count { !it.hidden } }

    override suspend fun getPostDetails(token: String, postId: String): Response<Post> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        val post = posts.find { it.postIdentifier == postId }
            ?: return errorGeneric(404, "No post with that identifier")
        val author = users.find { it.id == post.authorId }!!
        val avatar = approvedAvatarFor(post.authorId)

        return Response.success(Post(
            post.postIdentifier,
            post.imageUrl,
            post.caption,
            captionFont = post.captionFont,
            backgroundColor = post.backgroundColor,
            authorUsername = author.username,
            likeCount = post.likes.count(),
            isLiked = post.likes.contains(user.id),
            creationTime = post.creationTime.toString(),
            isReported = post.reports.contains(user.id),
            reportReason = post.reports[user.id],
            authorProfileImageUrl = avatar,
            authorProfileImageOriginalUrl = avatar
        ))
    }

    // ============================================================================================
    // comments
    // ============================================================================================

    override suspend fun commentOnPost(token: String, postId: String, request: CommentRequest): Response<CommentResponse> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        if (!posts.any { it.postIdentifier == postId }) return errorGeneric(404, "Post not found")

        // Create Thread
        val thread = CommentThreadMock(postId = postId)
        commentThreads.add(thread)

        // Create Comment
        val comment = CommentMock(authorId = user.id, body = request.commentText, bodyFormatting = request.bodyFormatting)
        thread.comments.add(comment)

        return Response.success(CommentResponse(thread.threadIdentifier, comment.commentIdentifier))
    }

    override suspend fun replyToThread(token: String, postId: String, threadId: String, request: CommentRequest): Response<CommentResponse> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        val thread = commentThreads.find { it.threadIdentifier == threadId && it.postId == postId }
            ?: return errorGeneric(404, "Thread not found")

        val comment = CommentMock(authorId = user.id, body = request.commentText, bodyFormatting = request.bodyFormatting)
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

        if (comment.authorId == user.id) return error(400, "Cannot report own comment")
        if (comment.reports.contains(user.id)) return error(400, "Cannot report comment twice")

        comment.reports[user.id] = request.reason
        if (comment.reports.size > 5) { // Stub limit
            comment.hidden = true
            comment.hiddenReason = "reports"
        }

        return Response.success(GenericResponse("Comment reported", null))
    }

    override suspend fun retractReportComment(token: String, postId: String, threadId: String, commentId: String): Response<GenericResponse> {
        val user = getAuthorizedUser(token) ?: return error(401, "Unauthorized")
        val comment = findComment(postId, threadId, commentId) ?: return error(404, "Comment not found")

        if (!comment.reports.contains(user.id)) return error(400, "Comment not reported yet")

        comment.reports.remove(user.id)
        // Un-hide only when reports were what hid it, mirroring the backend.
        if (comment.hidden && comment.hiddenReason == "reports" && comment.reports.size <= 5) { // Stub limit
            comment.hidden = false
            comment.hiddenReason = ""
        }
        return Response.success(GenericResponse("Comment report retracted", null))
    }

    override suspend fun getCommentsForPost(token: String, postId: String, batch: Int): Response<List<CommentThreadDto>> {
        getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        val threads = commentThreads.filter { it.postId == postId }
        val batched = getBatch(threads, batch, COMMENT_BATCH_SIZE)
        return Response.success(batched.map { CommentThreadDto(it.threadIdentifier) })
    }

    override suspend fun getCommentsForThread(token: String, threadId: String, batch: Int): Response<List<CommentDto>> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        val thread = commentThreads.find { it.threadIdentifier == threadId }
            ?: return errorGeneric(404, "Thread not found")

        val comments = thread.comments.filter { !it.hidden }.sortedBy { it.creationTime }
        val batched = getBatch(comments, batch, COMMENT_BATCH_SIZE)

        val dtos = batched.map { c ->
            val author = users.find { it.id == c.authorId }!!
            val avatar = approvedAvatarFor(c.authorId)
            CommentDto(
                c.commentIdentifier,
                c.body,
                author.username,
                c.creationTime.toString(),
                c.creationTime.toString(),
                c.likes.size,
                isLiked = c.likes.contains(user.id),
                isReported = c.reports.contains(user.id),
                reportReason = c.reports[user.id],
                authorProfileImageUrl = avatar,
                authorProfileImageOriginalUrl = avatar,
                bodyFormatting = c.bodyFormatting
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
            .filter { 
                it.username.contains(fragment, ignoreCase = true) && 
                it.id != currentUser?.id &&
                (currentUser == null || !currentUser.blockedBy.contains(it.id))
            }
            .take(10)
            .map { User(it.username, it.isVerified, approvedAvatarFor(it.id), approvedAvatarFor(it.id)) }
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
        user.following.remove(target.id)
        target.followers.remove(user.id)
        return Response.success(GenericResponse("User unfollowed", null))
    }

    override suspend fun toggleBlock(token: String, username: String): Response<GenericResponse> {
        val user = getAuthorizedUser(token) ?: return error(401, "Unauthorized")
        val target = users.find { it.username == username } ?: return error(404, "User not found")

        if (user.id == target.id) return error(404, "Cannot block self")

        if (user.blocked.contains(target.id)) {
            // Unblock
            user.blocked.remove(target.id)
            target.blockedBy.remove(user.id)
            return Response.success(GenericResponse("User unblocked", null))
        } else {
            // Block
            user.blocked.add(target.id)
            target.blockedBy.add(user.id)
            
            // Remove follow relationships
            if (user.following.contains(target.id)) {
                user.following.remove(target.id)
                target.followers.remove(user.id)
            }
            if (target.following.contains(user.id)) {
                target.following.remove(user.id)
                user.followers.remove(target.id)
            }
            
            return Response.success(GenericResponse("User blocked", null))
        }
    }

    override suspend fun getBlockedUsers(token: String): Response<List<User>> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        val blockedUsers = users
            .filter { user.blocked.contains(it.id) }
            .sortedBy { it.username }
            .map { User(it.username, it.isVerified, approvedAvatarFor(it.id), approvedAvatarFor(it.id)) }
        return Response.success(blockedUsers)
    }

    override suspend fun getFollowers(token: String): Response<List<User>> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        // The current user's followers are the users whose ids are in followers.
        val followers = users
            .filter { user.followers.contains(it.id) }
            .sortedBy { it.username }
            .map { User(it.username, it.isVerified, approvedAvatarFor(it.id), approvedAvatarFor(it.id)) }
        return Response.success(followers)
    }

    override suspend fun getFollowing(token: String): Response<List<User>> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        // The users the current user follows are the ids in following.
        val following = users
            .filter { user.following.contains(it.id) }
            .sortedBy { it.username }
            .map { User(it.username, it.isVerified, approvedAvatarFor(it.id), approvedAvatarFor(it.id)) }
        return Response.success(following)
    }

    override suspend fun getProfileDetails(token: String, username: String): Response<ProfileDetailsResponse> {
        val user = getAuthorizedUser(token) // Can be null if public profile view? Python code required login.
        val target = users.find { it.username == username } ?: return errorGeneric(404, "User not found")

        val postCount = posts.count { it.authorId == target.id }
        val isFollowing = user?.following?.contains(target.id) ?: false
        val isBlocked = user?.blocked?.contains(target.id) ?: false
        val isBlockedBy = user?.blockedBy?.contains(target.id) ?: false

        if (isBlockedBy) {
             return Response.success(ProfileDetailsResponse(
                target.username,
                0,
                0,
                0,
                false,
                isBlocked = isBlocked,
                membershipNumber = target.membershipNumber
            ))
        }

        // Only the approved photo is exposed; the stub has no separate compressed
        // bucket, so the compressed and original URLs are the same (issue #7).
        val liveAvatar = approvedAvatarFor(target.id)
        val isOwnProfile = user != null && user.id == target.id
        return Response.success(ProfileDetailsResponse(
            target.username,
            postCount,
            target.followers.size,
            target.following.size,
            isFollowing,
            isBlocked,
            membershipNumber = target.membershipNumber,
            profileImageUrl = liveAvatar,
            profileImageOriginalUrl = liveAvatar,
            // Owner-only moderation state, mirroring the backend: present only
            // when viewing your own profile.
            profileImageStatus = if (isOwnProfile) target.profileImageStatus else null,
            profileImageReasonCode = if (isOwnProfile) target.profileImageReasonCode else null,
            pendingProfileImageUrl = if (isOwnProfile) target.pendingProfileImageUrl else null
        ))
    }

    override suspend fun setProfilePhoto(token: String, request: SetProfilePhotoRequest): Response<SetProfilePhotoResponse> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        // The real backend stores the photo pending and classifies it off the
        // request path; the stub has no classifier, so — like the backend's
        // eager (no-Redis) mode — it approves immediately, while the response
        // still reports the initial "pending" state so clients exercise that path.
        user.profileImageUrl = request.imageUrl
        user.pendingProfileImageUrl = null
        user.profileImageStatus = "approved"
        user.profileImageReasonCode = null
        return Response.success(
            SetProfilePhotoResponse(
                profileImageStatus = "pending",
                message = "Your photo is being reviewed and will be shown once it is approved."
            )
        )
    }

    override suspend fun removeProfilePhoto(token: String): Response<RemoveProfilePhotoResponse> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        user.profileImageUrl = null
        user.pendingProfileImageUrl = null
        user.profileImageStatus = "none"
        user.profileImageReasonCode = null
        return Response.success(
            RemoveProfilePhotoResponse(
                profileImageStatus = "none",
                message = "Your profile photo has been removed."
            )
        )
    }

    // ============================================================================================
    // appeals
    // ============================================================================================

    private fun hasAppeal(targetId: String): Boolean = appeals.any { it.targetId == targetId }

    override suspend fun getHiddenPosts(token: String, batch: Int): Response<List<HiddenPost>> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        // Pending posts have nothing to appeal yet and final rejections are
        // terminal, so neither belongs on the appeals screen (#282).
        val hidden = posts.filter { it.authorId == user.id && it.hidden && isAppealable(it) }
            .sortedByDescending { it.creationTime }
        val dtos = getBatch(hidden, batch, POST_BATCH_SIZE).map {
            HiddenPost(
                it.postIdentifier,
                it.imageUrl,
                it.caption,
                captionFont = it.captionFont,
                backgroundColor = it.backgroundColor,
                hiddenReason = it.hiddenReason,
                hasAppeal = hasAppeal(it.postIdentifier)
            )
        }
        return Response.success(dtos)
    }

    override suspend fun getHiddenComments(token: String, batch: Int): Response<List<HiddenComment>> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        val hidden = commentThreads.flatMap { it.comments }
            .filter { it.authorId == user.id && it.hidden }
            .sortedByDescending { it.creationTime }
        val dtos = getBatch(hidden, batch, COMMENT_BATCH_SIZE).map {
            HiddenComment(
                it.commentIdentifier,
                it.body,
                bodyFormatting = it.bodyFormatting,
                hiddenReason = it.hiddenReason,
                hasAppeal = hasAppeal(it.commentIdentifier)
            )
        }
        return Response.success(dtos)
    }

    override suspend fun getMyAppeals(token: String, batch: Int): Response<List<MyAppeal>> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")
        val mine = appeals.filter { it.appellantId == user.id }
        val dtos = getBatch(mine, batch, POST_BATCH_SIZE).map {
            MyAppeal(it.appealIdentifier, it.targetType, it.status, it.reason, it.contentSnapshot, null)
        }
        return Response.success(dtos)
    }

    override suspend fun submitAppeal(token: String, request: SubmitAppealRequest): Response<SubmitAppealResponse> {
        val user = getAuthorizedUser(token) ?: return errorGeneric(401, "Unauthorized")

        val snapshot: String = when (request.targetType) {
            "post" -> {
                // Pending and final-rejected posts are not appealable (#282).
                val post = posts.find { it.postIdentifier == request.targetIdentifier && it.authorId == user.id && it.hidden && isAppealable(it) }
                    ?: return errorGeneric(400, "No appealable item with that identifier")
                post.caption
            }
            "comment" -> {
                val comment = commentThreads.flatMap { it.comments }
                    .find { it.commentIdentifier == request.targetIdentifier && it.authorId == user.id && it.hidden }
                    ?: return errorGeneric(400, "No appealable item with that identifier")
                comment.body
            }
            // Match the backend, which rejects any target_type other than
            // post/comment rather than treating it as a comment.
            else -> return errorGeneric(400, "Invalid target_type")
        }

        if (hasAppeal(request.targetIdentifier)) {
            return errorGeneric(400, "This item has already been appealed")
        }

        val appeal = AppealMock(
            appellantId = user.id,
            targetType = request.targetType,
            targetId = request.targetIdentifier,
            reason = request.reason,
            contentSnapshot = snapshot
        )
        appeals.add(appeal)
        return Response.success(SubmitAppealResponse(appeal.appealIdentifier))
    }

    // ============================================================================================
    // utils
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