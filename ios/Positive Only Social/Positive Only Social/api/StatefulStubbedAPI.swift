import Foundation

// Define a custom error to make debugging easier
struct SerializationError: Error, LocalizedError {
    var errorDescription: String? = "Failed to convert inner JSON data to a UTF-8 string."
}

// MARK: - In-Memory Data Models
// These structs simulate the Django database models.

// Public so the Settings tests can use it
struct MockUser {
    let id = UUID()
    var username: String
    var email: String
    var passwordHash: String // Storing plain text for mock purposes.
    var verificationToken: String? = nil
    var resetToken: String? = nil
    // The real backend starts accounts unverified and gates everything on the
    // emailed link; the stub has no inbox, so accounts start verified to keep
    // offline/demo mode usable.
    var emailVerified: Bool = true
    var emailVerificationToken: String? = nil
    var identityIsVerified: Bool = false
    var isAdult: Bool = false
    var blocked: [UUID] = []
    var blockedBy: [UUID] = []
    // Two-factor authentication (issue #348). A secret without the enabled
    // flag is a pending enrollment; recovery codes are removed as they are used.
    var totpSecret: String? = nil
    var totpEnabled: Bool = false
    var recoveryCodes: [String] = []

    init(username: String, email: String, passwordHash: String) {
        self.username = username
        self.email = email
        self.passwordHash = passwordHash
    }
}

// A pending two-factor login, issued by loginUser when the account has TOTP
// enabled and consumed by loginUser2FA.
fileprivate struct MockTwoFactorChallenge {
    let challengeToken: String
    let userId: UUID
    let rememberMe: Bool
    let ip: String
}

fileprivate struct MockUserFollow {
    let userFromId: UUID
    let userToId: UUID
}

// We let this one be seen so the Settings tests can use it
struct MockSession {
    let managementToken: String
    let userId: UUID
    let ip: String
}

fileprivate struct MockLoginCookie {
    let seriesIdentifier: String
    var token: String
    let userId: UUID
}

fileprivate struct MockPost {
    let postIdentifier = UUID().uuidString
    let authorId: UUID
    // Nil for a text-only post (#307).
    var imageURL: String?
    var caption: String
    var likes: [String] = [] // Usernames of likers
    var reports: [(username: String, reason: String)] = []
    var commentThreads: [MockCommentThread] = []
    var isHidden: Bool = false
    var hiddenReason: String = GVOAppConstants.emptyString
    /// Public reason code recorded by the (stubbed) async classifier (#282).
    var reasonCode: String? = nil
    let createdDate = Date()
}

fileprivate struct MockCommentThread {
    let commentThreadIdentifier = UUID().uuidString
    let postId: String
    var comments: [MockComment] = []
}

fileprivate struct MockComment {
    let commentIdentifier = UUID().uuidString
    let threadId: String
    var authorUsername: String
    var body: String
    var likes: [String] = []
    var reports: [(username: String, reason: String)] = []
    var isHidden: Bool = false
    var hiddenReason: String = GVOAppConstants.emptyString
    let createdDate = Date()
    var updatedDate = Date()
}

fileprivate struct MockAppeal {
    let appealIdentifier = UUID().uuidString
    let appellantId: UUID
    let targetType: String
    let targetId: String
    var reason: String
    var contentSnapshot: String
    var status: String = "pending"
    let createdDate = Date()
}


// MARK: - Stateful API Implementation
final class StatefulStubbedAPI: Networking {

    // The stub has no clock-based TOTP; this fixed code is the one the stub
    // accepts, mirroring the fixed codes in the website/Android stubs.
    static let stubTotpCode = "123456"

    // MARK: - In-Memory "Database"
    private var users: [MockUser] = []
    private var sessions: [MockSession] = []
    private var loginCookies: [MockLoginCookie] = []
    private var twoFactorChallenges: [MockTwoFactorChallenge] = []
    private var posts: [MockPost] = []
    private var commentThreads: [MockCommentThread] = []
    private var comments: [MockComment] = []
    private var appeals: [MockAppeal] = []
    private var userFollows: [MockUserFollow] = []

    // MARK: - Configuration
    public var simulatedLatency: TimeInterval = 0.1
    private let maxReportsBeforeHiding = 5
    private let awsStubBucket = "https://stub-bucket.s3.us-east-2.amazonaws.com/"
    public var pageSize = 2 // Make this small for easier testing
    public private(set) var getPostsInFeedCallCount = 0
    public private(set) var getPostsForFollowedUsersCallCount = 0
    public private(set) var getPostsForUserCallCount = 0
    public private(set) var getUsersMatchingFragmentCallCount = 0

    // MARK: - Public Finders
    func findSession(byToken token: String) -> MockSession? { sessions.first { $0.managementToken == token } }
    func findUser(byUsername name: String) -> MockUser? { users.first { $0.username == name } }
    
    // MARK: - Private Finders
    private func findUser(byUsernameOrEmail id: String) -> MockUser? { users.first { $0.username == id || $0.email == id } }
    private func findUser(byEmail email: String) -> MockUser? { users.first { $0.email == email } }
    private func findUser(byUsername name: String, andEmail email: String) -> MockUser? { users.first { $0.username == name && $0.email == email } }
    private func findUser(bySessionToken token: String) -> MockUser? {
        guard let session = findSession(byToken: token) else { return nil }
        return users.first { $0.id == session.userId }
    }
    private func findPost(byIdentifier id: String) -> MockPost? { posts.first { $0.postIdentifier == id } }
    private func findCommentThread(byIdentifier id: String) -> MockCommentThread? { commentThreads.first { $0.commentThreadIdentifier == id } }
    private func findComment(byIdentifier id: String) -> MockComment? { comments.first { $0.commentIdentifier == id } }
    private func isUserFollowing(from: UUID, to: UUID) -> Bool {
            userFollows.contains { $0.userFromId == from && $0.userToId == to }
    }

    // MARK: - Private Helpers
    /// Returns a single-object JSON response matching the real backend format.
    private func createSerializedResponse<T: Codable>(fields: T) throws -> Data {
        return try JSONEncoder().encode(fields)
    }

    /// Returns a JSON array response matching the real backend format.
    private func createSerializedListResponse<T: Codable>(fieldsList: [T]) throws -> Data {
        return try JSONEncoder().encode(fieldsList)
    }

    private func createEmptySuccessResponse() throws -> Data {
        return try JSONEncoder().encode(["message": "ok"])
    }
    private func simulateNetwork() async { try? await Task.sleep(for: .seconds(simulatedLatency)) }
    private func generateToken() -> String { UUID().uuidString.replacingOccurrences(of: "-", with: "") }

    // MARK: - Implementations
    
    func register(username: String, email: String, password: String, rememberMe: String, ip: String, dateOfBirth: String) async throws -> Data {
        await simulateNetwork()
        if findUser(byUsername: username) != nil || findUser(byEmail: email) != nil {
            throw APIError.badServerResponse(statusCode: 400) // "User already exists"
        }
        let newUser = MockUser(username: username, email: email, passwordHash: password)
        users.append(newUser)
        let newSession = MockSession(managementToken: generateToken(), userId: newUser.id, ip: ip)
        sessions.append(newSession)
        
        let wantsRememberMe = Bool(rememberMe.lowercased()) ?? false
        if wantsRememberMe {
            let cookie = MockLoginCookie(seriesIdentifier: UUID().uuidString, token: generateToken(), userId: newUser.id)
            loginCookies.append(cookie)
            struct Fields: Codable { let series_identifier, login_cookie_token, session_management_token, user_id: String }
            return try createSerializedResponse(fields: Fields(
                series_identifier: cookie.seriesIdentifier,
                login_cookie_token: cookie.token,
                session_management_token: newSession.managementToken,
                user_id: newUser.id.uuidString
            ))
        } else {
            struct Fields: Codable { let session_management_token, user_id: String }
            return try createSerializedResponse(fields: Fields(session_management_token: newSession.managementToken, user_id: newUser.id.uuidString))
        }
    }

    func loginUser(usernameOrEmail: String, password: String, rememberMe: String, ip: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(byUsernameOrEmail: usernameOrEmail) else { throw APIError.badServerResponse(statusCode: 400) }
        if user.passwordHash != password { throw APIError.badServerResponse(statusCode: 400) }

        // 2FA-enrolled accounts get a challenge instead of a session, mirroring
        // login_user in backend/user_system/views.py.
        if user.totpEnabled {
            // Only one challenge is live per user, matching login_user in the
            // backend — otherwise a stale challenge from an earlier attempt
            // would still be accepted after a newer login.
            twoFactorChallenges.removeAll { $0.userId == user.id }
            let challenge = MockTwoFactorChallenge(
                challengeToken: generateToken(),
                userId: user.id,
                rememberMe: Bool(rememberMe.lowercased()) ?? false,
                ip: ip
            )
            twoFactorChallenges.append(challenge)
            struct Fields: Codable { let two_factor_required: Bool; let challenge_token: String }
            return try createSerializedResponse(fields: Fields(two_factor_required: true, challenge_token: challenge.challengeToken))
        }

        sessions.removeAll { $0.userId == user.id }
        let newSession = MockSession(managementToken: generateToken(), userId: user.id, ip: ip)
        sessions.append(newSession)

        let wantsRememberMe = Bool(rememberMe.lowercased()) ?? false
        if wantsRememberMe {
            let cookie = MockLoginCookie(seriesIdentifier: UUID().uuidString, token: generateToken(), userId: user.id)
            loginCookies.append(cookie)
            struct Fields: Codable { let series_identifier, login_cookie_token, session_management_token, username, user_id: String }
            return try createSerializedResponse(fields: Fields(
                series_identifier: cookie.seriesIdentifier,
                login_cookie_token: cookie.token,
                session_management_token: newSession.managementToken,
                username: user.username,
                user_id: user.id.uuidString
            ))
        } else {
            struct Fields: Codable { let session_management_token, username, user_id: String }
            return try createSerializedResponse(fields: Fields(
                session_management_token: newSession.managementToken,
                username: user.username,
                user_id: user.id.uuidString
            ))
        }
    }

    func loginUserWithRememberMe(sessionManagementToken: String, seriesIdentifier: String, loginCookieToken: String, ip: String) async throws -> Data {
        await simulateNetwork()

        // Find the cookie and the associated user
        guard let cookieIndex = loginCookies.firstIndex(where: { $0.seriesIdentifier == seriesIdentifier && $0.token == loginCookieToken }),
              let user = users.first(where: { $0.id == loginCookies[cookieIndex].userId })
        else {
            // If tokens are invalid, throw an error
            throw APIError.badServerResponse(statusCode: 401) // Unauthorized
        }
        
        // On success, issue a new cookie token AND a new session token.
        // NOTE: This assumes the backend's intent is to grant a full session.
        
        // 1. Update the login cookie with a new token
        let newCookieToken = generateToken()
        loginCookies[cookieIndex].token = newCookieToken
        
        // 2. Create a new session for the user
        let newSession = MockSession(managementToken: generateToken(), userId: user.id, ip: ip)
        sessions.append(newSession)

        struct Fields: Codable {
            let login_cookie_token: String
            let session_management_token: String
        }
        return try createSerializedResponse(fields: Fields(
            login_cookie_token: newCookieToken,
            session_management_token: newSession.managementToken
        ))
    }


    func loginUser2FA(challengeToken: String, totpCode: String?, recoveryCode: String?, ip: String) async throws -> Data {
        await simulateNetwork()
        guard let challengeIndex = twoFactorChallenges.firstIndex(where: { $0.challengeToken == challengeToken }),
              let userIndex = users.firstIndex(where: { $0.id == twoFactorChallenges[challengeIndex].userId })
        else {
            throw APIError.serverError(statusCode: 400, serverMessage: "Invalid or expired challenge")
        }
        let challenge = twoFactorChallenges[challengeIndex]

        let codeOk: Bool
        if let totpCode = totpCode, recoveryCode == nil {
            codeOk = totpCode == Self.stubTotpCode
        } else if let recoveryCode = recoveryCode, totpCode == nil {
            // Recovery codes are single-use: consume on success.
            if let codeIndex = users[userIndex].recoveryCodes.firstIndex(of: recoveryCode) {
                users[userIndex].recoveryCodes.remove(at: codeIndex)
                codeOk = true
            } else {
                codeOk = false
            }
        } else {
            throw APIError.serverError(statusCode: 400, serverMessage: "Invalid fields ['TOTP_CODE', 'RECOVERY_CODE']")
        }
        guard codeOk else {
            throw APIError.serverError(statusCode: 400, serverMessage: "Invalid two-factor code")
        }

        twoFactorChallenges.remove(at: challengeIndex)
        let user = users[userIndex]

        sessions.removeAll { $0.userId == user.id }
        // Record the IP this second step came from, not the one from the
        // password step — they can differ, and the other login endpoints all
        // store the IP of the request that issued the session.
        let newSession = MockSession(managementToken: generateToken(), userId: user.id, ip: ip)
        sessions.append(newSession)

        if challenge.rememberMe {
            let cookie = MockLoginCookie(seriesIdentifier: UUID().uuidString, token: generateToken(), userId: user.id)
            loginCookies.append(cookie)
            struct Fields: Codable { let series_identifier, login_cookie_token, session_management_token, username, user_id: String }
            return try createSerializedResponse(fields: Fields(
                series_identifier: cookie.seriesIdentifier,
                login_cookie_token: cookie.token,
                session_management_token: newSession.managementToken,
                username: user.username,
                user_id: user.id.uuidString
            ))
        } else {
            struct Fields: Codable { let session_management_token, username, user_id: String }
            return try createSerializedResponse(fields: Fields(
                session_management_token: newSession.managementToken,
                username: user.username,
                user_id: user.id.uuidString
            ))
        }
    }

    func setupTotp(sessionManagementToken: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken),
              let userIndex = users.firstIndex(where: { $0.id == user.id })
        else { throw APIError.badServerResponse(statusCode: 401) }
        if users[userIndex].totpEnabled {
            throw APIError.serverError(statusCode: 400, serverMessage: "Two-factor authentication is already enabled")
        }
        // Re-running setup before confirming simply replaces the pending secret.
        // Use the RFC 4648 Base32 alphabet (A-Z, 2-7) so the otpauth:// URI is a
        // valid TOTP secret that real authenticator apps and QR parsers accept.
        let base32Alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        let secret = String((0..<32).map { _ in base32Alphabet.randomElement()! })
        users[userIndex].totpSecret = secret

        struct Fields: Codable { let totp_secret, otpauth_uri: String }
        return try createSerializedResponse(fields: Fields(
            totp_secret: secret,
            otpauth_uri: "otpauth://totp/Positive%20Only%20Social:\(user.email)?secret=\(secret)&issuer=Positive%20Only%20Social"
        ))
    }

    func confirmTotp(sessionManagementToken: String, totpCode: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken),
              let userIndex = users.firstIndex(where: { $0.id == user.id })
        else { throw APIError.badServerResponse(statusCode: 401) }
        if users[userIndex].totpEnabled {
            throw APIError.serverError(statusCode: 400, serverMessage: "Two-factor authentication is already enabled")
        }
        guard users[userIndex].totpSecret != nil else {
            throw APIError.serverError(statusCode: 400, serverMessage: "Two-factor setup has not been started")
        }
        guard totpCode == Self.stubTotpCode else {
            throw APIError.serverError(statusCode: 400, serverMessage: "Invalid two-factor code")
        }
        users[userIndex].totpEnabled = true
        users[userIndex].recoveryCodes = (0..<10).map { _ in String(generateToken().lowercased().prefix(10)) }

        struct Fields: Codable { let totp_enabled: Bool; let recovery_codes: [String] }
        return try createSerializedResponse(fields: Fields(totp_enabled: true, recovery_codes: users[userIndex].recoveryCodes))
    }

    func disableTotp(sessionManagementToken: String, password: String, totpCode: String?, recoveryCode: String?) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken),
              let userIndex = users.firstIndex(where: { $0.id == user.id })
        else { throw APIError.badServerResponse(statusCode: 401) }
        guard users[userIndex].totpEnabled else {
            throw APIError.serverError(statusCode: 400, serverMessage: "Two-factor authentication is not enabled")
        }
        guard users[userIndex].passwordHash == password else {
            throw APIError.serverError(statusCode: 400, serverMessage: "Invalid password")
        }

        let codeOk: Bool
        if let totpCode = totpCode, recoveryCode == nil {
            codeOk = totpCode == Self.stubTotpCode
        } else if let recoveryCode = recoveryCode, totpCode == nil {
            if let codeIndex = users[userIndex].recoveryCodes.firstIndex(of: recoveryCode) {
                users[userIndex].recoveryCodes.remove(at: codeIndex)
                codeOk = true
            } else {
                codeOk = false
            }
        } else {
            codeOk = false
        }
        guard codeOk else {
            throw APIError.serverError(statusCode: 400, serverMessage: "Invalid two-factor code")
        }

        users[userIndex].totpSecret = nil
        users[userIndex].totpEnabled = false
        users[userIndex].recoveryCodes = []
        twoFactorChallenges.removeAll { $0.userId == user.id }

        struct Fields: Codable { let totp_enabled: Bool }
        return try createSerializedResponse(fields: Fields(totp_enabled: false))
    }

    func verifyEmail(verificationToken: String) async throws -> Data {
        await simulateNetwork()
        guard let userIndex = users.firstIndex(where: { $0.emailVerificationToken != nil && $0.emailVerificationToken == verificationToken }) else {
            throw APIError.serverError(statusCode: 400, serverMessage: "Invalid or expired verification token")
        }
        users[userIndex].emailVerified = true
        users[userIndex].emailVerificationToken = nil
        return try createEmptySuccessResponse()
    }

    func resendVerificationEmail(usernameOrEmail: String) async throws -> Data {
        await simulateNetwork()
        guard let userIndex = users.firstIndex(where: { $0.username == usernameOrEmail || $0.email == usernameOrEmail }) else {
            throw APIError.serverError(statusCode: 400, serverMessage: "No user with that username or email")
        }
        guard !users[userIndex].emailVerified else {
            throw APIError.serverError(statusCode: 400, serverMessage: "Email already verified")
        }
        let stubToken = "stub_email_verification_token_\(users[userIndex].username)"
        users[userIndex].emailVerificationToken = stubToken
        NSLog("%@", "Email verification token for \(users[userIndex].username) is: \(stubToken)")
        return try createEmptySuccessResponse()
    }

    func requestPasswordReset(usernameOrEmail: String) async throws -> Data {
        await simulateNetwork()
        guard let userIndex = users.firstIndex(where: { $0.username == usernameOrEmail || $0.email == usernameOrEmail }) else { throw APIError.badServerResponse(statusCode: 400) }
        let stubToken = "stub_verification_token_\(users[userIndex].username)"
        users[userIndex].verificationToken = stubToken
        NSLog("%@", "Password reset verification token for \(users[userIndex].username) is: \(stubToken)")
        return try createEmptySuccessResponse()
    }

    func verifyPasswordReset(usernameOrEmail: String, verificationToken: String) async throws -> Data {
        await simulateNetwork()
        guard let userIndex = users.firstIndex(where: { $0.username == usernameOrEmail || $0.email == usernameOrEmail }) else { throw APIError.badServerResponse(statusCode: 400) }
        guard users[userIndex].verificationToken == verificationToken else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        let resetToken = "stub_reset_token_\(users[userIndex].username)"
        users[userIndex].verificationToken = nil
        users[userIndex].resetToken = resetToken
        struct VerifyResetResponseFields: Codable {
            let message: String
            let reset_token: String
        }
        return try createSerializedResponse(fields: VerifyResetResponseFields(message: "Verification successful", reset_token: resetToken))
    }

    func resetPassword(username: String, email: String, newPassword: String, resetToken: String) async throws -> Data {
        await simulateNetwork()
        guard let userIndex = users.firstIndex(where: { $0.username == username && $0.email == email }),
              users[userIndex].resetToken == resetToken else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        users[userIndex].passwordHash = newPassword
        users[userIndex].resetToken = nil
        return try createEmptySuccessResponse()
    }

    func logoutUser(sessionManagementToken: String) async throws -> Data {
        await simulateNetwork()
        if let sessionIndex = sessions.firstIndex(where: { $0.managementToken == sessionManagementToken }) {
            sessions.remove(at: sessionIndex)
            return try createEmptySuccessResponse()
        }
        throw APIError.badServerResponse(statusCode: 400)
    }

    func deleteUser(sessionManagementToken: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        sessions.removeAll { $0.userId == user.id }
        posts.removeAll { $0.authorId == user.id }
        users.removeAll { $0.id == user.id }
        return try createEmptySuccessResponse()
    }
    
    func verifyIdentity(sessionManagementToken: String, dateOfBirth: String) async throws -> Data {
        await simulateNetwork()
        
        // 1. Retrieve User and Index
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let userIndex = users.firstIndex(where: { $0.id == user.id }) else { throw APIError.badServerResponse(statusCode: 400) }
        
        // 2. Parse the Date of Birth String
        // Note: Ensure your input string matches this format (e.g., "1990-01-01")
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = TimeZone(secondsFromGMT: 0) // Ensure consistency
        
        guard let birthDate = formatter.date(from: dateOfBirth) else {
            // Throw an error if the date format is invalid
            throw APIError.badServerResponse(statusCode: 400) 
        }
        
        // 3. Calculate Age Logic
        // We calculate the date exactly 18 years ago from "now"
        let calendar = Calendar.current
        if let eighteenYearsAgo = calendar.date(byAdding: .year, value: -18, to: Date()) {
            
            // If the birth date is earlier than or equal to 18 years ago, they are an adult
            if birthDate <= eighteenYearsAgo {
                users[userIndex].isAdult = true
            } else {
                users[userIndex].isAdult = false
            }
        }
        
        // 4. Complete Verification
        users[userIndex].identityIsVerified = true
        return try createEmptySuccessResponse()
    }
        
    func createUploadUrl(sessionManagementToken: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        // Mirror the backend: a fresh key under the user's prefix, returned as
        // both a "presigned" upload URL and the canonical image URL.
        let imageUrl = "\(awsStubBucket)\(user.id)/stub-\(UUID().uuidString).jpeg"
        struct Fields: Codable { let upload_url: String; let image_url: String }
        return try createSerializedResponse(fields: Fields(upload_url: "\(imageUrl)?X-Amz-Signature=stub", image_url: imageUrl))
    }

    func makePost(sessionManagementToken: String, imageURL: String?, caption: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        // Stub pre-filter, mirroring the backend's cheap inline check (#282): a
        // blatant hit is rejected immediately and the post is never created.
        if caption.contains("negative") {
            throw APIError.serverError(statusCode: 400, serverMessage: "Text is not positive because your caption did not meet our positivity guidelines. This decision is final and cannot be appealed.")
        }
        var newPost = MockPost(authorId: user.id, imageURL: imageURL, caption: caption)
        newPost.isHidden = true
        newPost.hiddenReason = "pending_classification"
        // The real backend classifies asynchronously in a worker; the stub
        // resolves instantly (like the backend's eager dev mode) but still
        // returns the pending response, so clients exercise the reconcile
        // path. Tests can set `deferClassification` to keep the post pending
        // until resolvePendingClassifications() plays the worker's role.
        if !deferClassification {
            classify(&newPost)
        }
        posts.append(newPost)
        struct Fields: Codable {
            let post_identifier: String
            let status: String
            let hidden: Bool
            let hidden_reason: String
            let message: String
        }
        return try createSerializedResponse(fields: Fields(
            post_identifier: newPost.postIdentifier,
            status: "pending",
            hidden: true,
            hidden_reason: "pending_classification",
            message: "Your post is being reviewed and will be visible to others once it is approved."
        ))
    }

    /// When true, makePost leaves new posts in pending_classification until
    /// resolvePendingClassifications() is called, so tests can exercise the
    /// clients' reconcile path (#282).
    public var deferClassification = false

    /// Plays the async worker's role for tests: classifies every post still
    /// pending (#282).
    public func resolvePendingClassifications() {
        for index in posts.indices where posts[index].hiddenReason == "pending_classification" {
            classify(&posts[index])
        }
    }

    /// Stubbed async classifier (#282): a caption containing "borderline"
    /// becomes an appealable rejection; everything else is approved.
    private func classify(_ post: inout MockPost) {
        if post.caption.contains("borderline") {
            post.isHidden = true
            post.hiddenReason = "classifier"
            post.reasonCode = "guidelines"
        } else {
            post.isHidden = false
            post.hiddenReason = ""
        }
    }

    /// Author-facing classification status, mirroring Post.classification_status.
    private func classificationStatus(_ post: MockPost) -> String {
        switch post.hiddenReason {
        case "pending_classification": return "pending"
        case "classifier": return "rejected"
        case "classifier_final": return "rejected_final"
        default: return "approved"
        }
    }

    private func isAppealable(_ post: MockPost) -> Bool {
        post.isHidden && post.hiddenReason != "pending_classification" && post.hiddenReason != "classifier_final"
    }

    func getPostStatus(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let post = posts.first(where: { $0.postIdentifier == postIdentifier && $0.authorId == user.id }) else {
            throw APIError.serverError(statusCode: 400, serverMessage: "No post with that identifier by that user")
        }
        let status = classificationStatus(post)
        let message: String?
        switch status {
        case "pending":
            message = "Your post is being reviewed and will be visible to others once it is approved."
        case "rejected":
            message = "Your post did not pass automated review. It is hidden for now but you can appeal the decision."
        case "rejected_final":
            message = "Your post did not pass automated review. This decision is final and cannot be appealed."
        default:
            message = nil
        }
        struct Fields: Codable {
            let post_identifier: String
            let status: String
            let reason_code: String?
            let appealable: Bool
            let hidden: Bool
            let hidden_reason: String
            let message: String?
        }
        return try createSerializedResponse(fields: Fields(
            post_identifier: post.postIdentifier,
            status: status,
            reason_code: post.reasonCode,
            appealable: isAppealable(post),
            hidden: post.isHidden,
            hidden_reason: post.hiddenReason,
            message: message
        ))
    }

    func deletePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let postIndex = posts.firstIndex(where: { $0.postIdentifier == postIdentifier && $0.authorId == user.id }) else { throw APIError.badServerResponse(statusCode: 400) }
        posts.remove(at: postIndex)
        return try createEmptySuccessResponse()
    }

    func reportPost(sessionManagementToken: String, postIdentifier: String, reason: String) async throws -> Data {
        await simulateNetwork()
        guard let reporter = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let postIndex = posts.firstIndex(where: { $0.postIdentifier == postIdentifier }) else { throw APIError.badServerResponse(statusCode: 400) }
        if posts[postIndex].authorId == reporter.id { throw APIError.badServerResponse(statusCode: 400) }
        if posts[postIndex].reports.contains(where: { $0.username == reporter.username }) { throw APIError.badServerResponse(statusCode: 400) }
        
        posts[postIndex].reports.append((reporter.username, reason))
        if posts[postIndex].reports.count > maxReportsBeforeHiding {
            posts[postIndex].isHidden = true
            posts[postIndex].hiddenReason = "reports"
        }
        return try createEmptySuccessResponse()
    }

    func retractReportPost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        await simulateNetwork()
        guard let retractor = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let postIndex = posts.firstIndex(where: { $0.postIdentifier == postIdentifier }) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let reportIndex = posts[postIndex].reports.firstIndex(where: { $0.username == retractor.username }) else { throw APIError.badServerResponse(statusCode: 400) }

        posts[postIndex].reports.remove(at: reportIndex)
        // Un-hide only when reports were what hid it, mirroring the backend.
        if posts[postIndex].isHidden && posts[postIndex].hiddenReason == "reports"
            && posts[postIndex].reports.count <= maxReportsBeforeHiding {
            posts[postIndex].isHidden = false
            posts[postIndex].hiddenReason = ""
        }
        return try createEmptySuccessResponse()
    }

    func likePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        await simulateNetwork()
        guard let liker = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let postIndex = posts.firstIndex(where: { $0.postIdentifier == postIdentifier }) else { throw APIError.badServerResponse(statusCode: 400) }
        if posts[postIndex].authorId == liker.id { throw APIError.badServerResponse(statusCode: 400) }
        if posts[postIndex].likes.contains(liker.username) { throw APIError.badServerResponse(statusCode: 400) }
        
        posts[postIndex].likes.append(liker.username)
        return try createEmptySuccessResponse()
    }

    func unlikePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        await simulateNetwork()
        guard let unliker = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let postIndex = posts.firstIndex(where: { $0.postIdentifier == postIdentifier }) else { throw APIError.badServerResponse(statusCode: 400) }
        if posts[postIndex].authorId == unliker.id { throw APIError.badServerResponse(statusCode: 400) }
        guard let likeIndex = posts[postIndex].likes.firstIndex(of: unliker.username) else { throw APIError.badServerResponse(statusCode: 400) }
        
        posts[postIndex].likes.remove(at: likeIndex)
        return try createEmptySuccessResponse()
    }

    func getPostsInFeed(sessionManagementToken: String, batch: Int) async throws -> Data {
        getPostsInFeedCallCount += 1 // Track call count
        await simulateNetwork()
        
        guard let user = findUser(bySessionToken: sessionManagementToken) else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        
        // Get *all* relevant posts, sorted
        let relevantPosts = posts
            .filter { post in
                post.authorId != user.id && 
                !post.isHidden &&
                !user.blocked.contains(post.authorId) &&
                !user.blockedBy.contains(post.authorId)
            }
            .sorted { $0.createdDate > $1.createdDate }

        let startIndex = batch * pageSize
        
        // Check if the requested page is beyond the available posts
        guard startIndex < relevantPosts.count else {
            // Return an empty list, NOT an error
            return try createSerializedListResponse(fieldsList: [Fields]())
        }
        
        let endIndex = min(startIndex + pageSize, relevantPosts.count)
        let paginatedPosts = Array(relevantPosts[startIndex..<endIndex])

        struct Fields: Codable { let post_identifier: String; let image_url: String?; let caption: String; let author_username: String }

        let fieldObjects = paginatedPosts.map {
            let post = $0
            let authorUsername = users.first(where: { $0.id == post.authorId })?.username ?? "Unknown User"
            return Fields(post_identifier: $0.postIdentifier, image_url: $0.imageURL, caption: $0.caption, author_username: authorUsername)
        }

        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func getPostsForFollowedUsers(sessionManagementToken: String, batch: Int) async throws -> Data {
        getPostsForFollowedUsersCallCount+=1
        await simulateNetwork()
        
        // 1. Authenticate the user
        guard let currentUser = findUser(bySessionToken: sessionManagementToken) else {
            throw APIError.badServerResponse(statusCode: 401) // Unauthorized
        }
        
        // 2. Find all user IDs that the current user follows
        let followedUserIDs = userFollows
            .filter { $0.userFromId == currentUser.id }
            .map { $0.userToId }
        
        // 3. Get all posts from those users, filtering out hidden posts
        let relevantPosts = posts
            .filter { post in
                // Post author is in the followed list AND post is not hidden
                followedUserIDs.contains(post.authorId) && 
                !post.isHidden &&
                !currentUser.blocked.contains(post.authorId) &&
                !currentUser.blockedBy.contains(post.authorId)
            }
            .sorted { $0.createdDate > $1.createdDate } // Sort by newest first
        
        let startIndex = batch * pageSize
        
        // Check if the requested page is beyond the available posts
        guard startIndex < relevantPosts.count else {
            // Return an empty list, NOT an error
            return try createSerializedListResponse(fieldsList: [Fields]())
        }
        
        let endIndex = min(startIndex + pageSize, relevantPosts.count)
        let paginatedPosts = Array(relevantPosts[startIndex..<endIndex])

        // 5. Format the response (matching getPostsInFeed)
        struct Fields: Codable { let post_identifier: String; let image_url: String?; let caption: String; let author_username: String }
        
        let fieldObjects = paginatedPosts.map {
            let post = $0
            let authorUsername = users.first(where: { $0.id == post.authorId })?.username ?? "Unknown User"
            return Fields(post_identifier: $0.postIdentifier, image_url: $0.imageURL, caption: $0.caption, author_username: authorUsername)
        }
        
        // 6. Return the serialized list
        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func getPostsForUser(sessionManagementToken: String, username: String, batch: Int) async throws -> Data {
        getPostsForUserCallCount += 1
        await simulateNetwork()
        
        guard findUser(bySessionToken: sessionManagementToken) != nil else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        guard let targetUser = findUser(byUsername: username) else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        
        let user = findUser(bySessionToken: sessionManagementToken)!
        if user.blocked.contains(targetUser.id) || targetUser.blocked.contains(user.id) {
             return try createSerializedListResponse(fieldsList: [Fields]())
        }

        // Mirrors the backend's visible_posts: authors see their own hidden
        // posts (pending, appealable, report-hidden) in their grid; everyone
        // else only sees live ones. Final-rejection tombstones are visible to
        // nobody (#282).
        let isOwnGrid = user.id == targetUser.id
        let relevantPosts = posts
            .filter { $0.authorId == targetUser.id && $0.hiddenReason != "classifier_final" }
            .filter { isOwnGrid || !$0.isHidden }
            .sorted { $0.createdDate > $1.createdDate } // Sort newest first

        let startIndex = batch * pageSize
        guard startIndex < relevantPosts.count else {
            // Return an empty list, NOT an error
            return try createSerializedListResponse(fieldsList: [Fields]())
        }

        let endIndex = min(startIndex + pageSize, relevantPosts.count)
        let paginatedPosts = Array(relevantPosts[startIndex..<endIndex])

        // Author-only classification fields (#282) are included when viewing
        // one's own grid, mirroring the backend payload.
        struct Fields: Codable {
            let post_identifier: String
            let image_url: String?
            let caption: String
            let author_username: String
            let status: String?
            let hidden: Bool?
            let hidden_reason: String?
            let appealable: Bool?
        }

        let fieldObjects = paginatedPosts.map {
            let post = $0
            let authorUsername = users.first(where: { $0.id == post.authorId })?.username ?? "Unknown User"
            return Fields(
                post_identifier: $0.postIdentifier,
                image_url: $0.imageURL,
                caption: $0.caption,
                author_username: authorUsername,
                status: isOwnGrid ? classificationStatus(post) : nil,
                hidden: isOwnGrid ? post.isHidden : nil,
                hidden_reason: isOwnGrid ? post.hiddenReason : nil,
                appealable: isOwnGrid ? isAppealable(post) : nil
            )
        }

        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func getPostDetails(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 401) }
        guard let post = findPost(byIdentifier: postIdentifier) else { throw APIError.badServerResponse(statusCode: 400) }
        struct Fields: Codable {
            let post_identifier: String
            let image_url: String?
            let caption: String
            //TODO: eBlender rename to camelCase creationTime (via CodingKeys).
            let creation_time: String
            let post_likes: Int
            let is_liked: Bool
            let is_reported: Bool
            let report_reason: String?
            let author_username: String
        }
        let userReport = post.reports.first(where: { $0.username == user.username })
        let fields = Fields(
            post_identifier: post.postIdentifier,
            image_url: post.imageURL,
            caption: post.caption,
            // Mirror Django's DjangoJSONEncoder, which emits a colon-separated UTC
            // offset with fractional seconds (e.g. "…+00:00"), not a "Z" suffix, so
            // the client's date parsing is exercised against the real backend format.
            creation_time: post.createdDate.formatted(
                Date.ISO8601FormatStyle().year().month().day()
                    .time(includingFractionalSeconds: true)
                    .timeZone(separator: .colon)
            ),
            post_likes: post.likes.count,
            is_liked: post.likes.contains(user.username),
            is_reported: userReport != nil,
            report_reason: userReport?.reason,
            author_username: users.first(where: {$0.id == post.authorId})?.username ?? "Unknown User"
        )
        return try createSerializedResponse(fields: fields)
    }

    func commentOnPost(sessionManagementToken: String, postIdentifier: String, commentText: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard findPost(byIdentifier: postIdentifier) != nil else { throw APIError.badServerResponse(statusCode: 400) }

        var newThread = MockCommentThread(postId: postIdentifier)
        let newComment = MockComment(threadId: newThread.commentThreadIdentifier, authorUsername: user.username, body: commentText)
        newThread.comments.append(newComment)
        
        comments.append(newComment)
        commentThreads.append(newThread)
        
        struct Fields: Codable { let comment_thread_identifier, comment_identifier: String }
        let fields = Fields(comment_thread_identifier: newThread.commentThreadIdentifier, comment_identifier: newComment.commentIdentifier)
        return try createSerializedResponse(fields: fields)
    }

    func replyToCommentThread(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentText: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let threadIndex = commentThreads.firstIndex(where: { $0.commentThreadIdentifier == commentThreadIdentifier }) else { throw APIError.badServerResponse(statusCode: 400) }

        let newComment = MockComment(threadId: commentThreadIdentifier, authorUsername: user.username, body: commentText)
        commentThreads[threadIndex].comments.append(newComment)
        comments.append(newComment)
        
        struct Fields: Codable { let comment_identifier: String }
        return try createSerializedResponse(fields: Fields(comment_identifier: newComment.commentIdentifier))
    }

    func likeComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        await simulateNetwork()
        guard let liker = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let commentIndex = comments.firstIndex(where: { $0.commentIdentifier == commentIdentifier }) else { throw APIError.badServerResponse(statusCode: 400) }
        if comments[commentIndex].authorUsername == liker.username { throw APIError.badServerResponse(statusCode: 400) }
        if comments[commentIndex].likes.contains(liker.username) { throw APIError.badServerResponse(statusCode: 400) }

        comments[commentIndex].likes.append(liker.username)
        return try createEmptySuccessResponse()
    }

    func unlikeComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        await simulateNetwork()
        guard let unliker = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let commentIndex = comments.firstIndex(where: { $0.commentIdentifier == commentIdentifier }) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let likeIndex = comments[commentIndex].likes.firstIndex(of: unliker.username) else { throw APIError.badServerResponse(statusCode: 400) }
        
        comments[commentIndex].likes.remove(at: likeIndex)
        return try createEmptySuccessResponse()
    }

    func deleteComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let commentIndex = comments.firstIndex(where: { $0.commentIdentifier == commentIdentifier && $0.authorUsername == user.username }) else { throw APIError.badServerResponse(statusCode: 400) }
        
        comments.remove(at: commentIndex)
        // Also remove from the thread's comment list
        if let threadIndex = commentThreads.firstIndex(where: { $0.commentThreadIdentifier == commentThreadIdentifier }) {
            commentThreads[threadIndex].comments.removeAll(where: { $0.commentIdentifier == commentIdentifier })
        }
        return try createEmptySuccessResponse()
    }

    func reportComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String, reason: String) async throws -> Data {
        await simulateNetwork()
        guard let reporter = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let commentIndex = comments.firstIndex(where: { $0.commentIdentifier == commentIdentifier }) else { throw APIError.badServerResponse(statusCode: 400) }
        if comments[commentIndex].authorUsername == reporter.username { throw APIError.badServerResponse(statusCode: 400) }
        if comments[commentIndex].reports.contains(where: { $0.username == reporter.username }) { throw APIError.badServerResponse(statusCode: 400) }
        
        comments[commentIndex].reports.append((reporter.username, reason))
        if comments[commentIndex].reports.count > maxReportsBeforeHiding {
            comments[commentIndex].isHidden = true
            comments[commentIndex].hiddenReason = "reports"
        }
        return try createEmptySuccessResponse()
    }

    func retractReportComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        await simulateNetwork()
        guard let retractor = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let commentIndex = comments.firstIndex(where: { $0.commentIdentifier == commentIdentifier }) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let reportIndex = comments[commentIndex].reports.firstIndex(where: { $0.username == retractor.username }) else { throw APIError.badServerResponse(statusCode: 400) }

        comments[commentIndex].reports.remove(at: reportIndex)
        // Un-hide only when reports were what hid it, mirroring the backend.
        if comments[commentIndex].isHidden && comments[commentIndex].hiddenReason == "reports"
            && comments[commentIndex].reports.count <= maxReportsBeforeHiding {
            comments[commentIndex].isHidden = false
            comments[commentIndex].hiddenReason = ""
        }
        return try createEmptySuccessResponse()
    }

    func getCommentsForPost(sessionManagementToken: String, postIdentifier: String, batch: Int) async throws -> Data {
        await simulateNetwork()
        guard findUser(bySessionToken: sessionManagementToken) != nil else { throw APIError.badServerResponse(statusCode: 401) }
        let relevantThreads = commentThreads.filter { $0.postId == postIdentifier }
        
        // If there are no threads return gracefully
        if relevantThreads.isEmpty {
            return try createSerializedListResponse(fieldsList: [Fields]())
        }

        struct Fields: Codable { let comment_thread_identifier: String }
        let fieldObjects = relevantThreads.map { Fields(comment_thread_identifier: $0.commentThreadIdentifier) }
        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func getCommentsForThread(sessionManagementToken: String, commentThreadIdentifier: String, batch: Int) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 401) }
        let relevantComments = comments.filter { $0.threadId == commentThreadIdentifier && !$0.isHidden }.sorted { $0.createdDate < $1.createdDate }

        if relevantComments.isEmpty {
            // If there are no comments return gracefully
            return try createSerializedListResponse(fieldsList: [Fields]())
        }

        struct Fields: Codable {
            let comment_identifier, body, author_username: String
            let creation_time, updated_time: String
            let comment_likes: Int
            let is_liked: Bool
            let is_reported: Bool
            let report_reason: String?
        }

        let dateFormatter = ISO8601DateFormatter()
        let fieldObjects = relevantComments.map { comment in
            let userReport = comment.reports.first(where: { $0.username == user.username })
            return Fields(comment_identifier: comment.commentIdentifier, body: comment.body, author_username: comment.authorUsername,
                   creation_time: dateFormatter.string(from: comment.createdDate),
                   updated_time: dateFormatter.string(from: comment.updatedDate),
                   comment_likes: comment.likes.count,
                   is_liked: comment.likes.contains(user.username),
                   is_reported: userReport != nil,
                   report_reason: userReport?.reason)
        }
        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func getUsersMatchingFragment(sessionManagementToken: String, usernameFragment: String) async throws -> Data {
        getUsersMatchingFragmentCallCount += 1
        await simulateNetwork()
        guard findUser(bySessionToken: sessionManagementToken) != nil else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        let matchingUsers = users.filter { 
            $0.username.lowercased().starts(with: usernameFragment.lowercased()) &&
            !findUser(bySessionToken: sessionManagementToken)!.blockedBy.contains($0.id)
        }
        
        struct Fields: Codable { let username: String; let identity_is_verified: Bool }
        let fieldObjects = matchingUsers.map { Fields(username: $0.username, identity_is_verified: $0.identityIsVerified) }
        return try createSerializedListResponse(fieldsList: fieldObjects)
    }
    
    func getBlockedUsers(sessionManagementToken: String) async throws -> Data {
        await simulateNetwork()
        guard let currentUser = findUser(bySessionToken: sessionManagementToken) else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        let blockedUsers = users
            .filter { currentUser.blocked.contains($0.id) }
            .sorted { $0.username < $1.username }

        struct Fields: Codable { let username: String; let identity_is_verified: Bool }
        let fieldObjects = blockedUsers.map { Fields(username: $0.username, identity_is_verified: $0.identityIsVerified) }
        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func followUser(sessionManagementToken: String, username: String) async throws -> Data {
        await simulateNetwork()
        guard let currentUser = findUser(bySessionToken: sessionManagementToken) else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        guard let userToFollow = findUser(byUsername: username) else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        
        if currentUser.id == userToFollow.id {
            throw APIError.badServerResponse(statusCode: 400) // Can't follow self
        }
        
        if isUserFollowing(from: currentUser.id, to: userToFollow.id) {
            throw APIError.badServerResponse(statusCode: 400) // Already following
        }
        
        let newFollow = MockUserFollow(userFromId: currentUser.id, userToId: userToFollow.id)
        userFollows.append(newFollow)
        
        return try createEmptySuccessResponse()
    }
        
    func unfollowUser(sessionManagementToken: String, username: String) async throws -> Data {
        await simulateNetwork()
        guard let currentUser = findUser(bySessionToken: sessionManagementToken) else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        guard let userToUnfollow = findUser(byUsername: username) else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        
        guard let followIndex = userFollows.firstIndex(where: {
            $0.userFromId == currentUser.id && $0.userToId == userToUnfollow.id
        }) else {
            throw APIError.badServerResponse(statusCode: 400) // Not following
        }
        
        userFollows.remove(at: followIndex)
        return try createEmptySuccessResponse()
    }

    func toggleBlock(sessionManagementToken: String, username: String) async throws -> Data {
        await simulateNetwork()
        guard let currentUser = findUser(bySessionToken: sessionManagementToken) else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        guard let userToBlock = findUser(byUsername: username) else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        
        if currentUser.id == userToBlock.id {
            throw APIError.badServerResponse(statusCode: 400) // Can't block self
        }
        
        // Find indices to update structs in array
        guard let currentIndex = users.firstIndex(where: {$0.id == currentUser.id}),
              let targetIndex = users.firstIndex(where: {$0.id == userToBlock.id}) else {
             throw APIError.badServerResponse(statusCode: 500)
        }
        
        if users[currentIndex].blocked.contains(userToBlock.id) {
            // Unblock
            users[currentIndex].blocked.removeAll { $0 == userToBlock.id }
            users[targetIndex].blockedBy.removeAll { $0 == currentUser.id }
        } else {
            // Block
            users[currentIndex].blocked.append(userToBlock.id)
            users[targetIndex].blockedBy.append(currentUser.id)
            
            // Unfollow logic
            if isUserFollowing(from: currentUser.id, to: userToBlock.id) {
                 userFollows.removeAll { $0.userFromId == currentUser.id && $0.userToId == userToBlock.id }
            }
            if isUserFollowing(from: userToBlock.id, to: currentUser.id) {
                 userFollows.removeAll { $0.userFromId == userToBlock.id && $0.userToId == currentUser.id }
            }
        }
        
        return try createEmptySuccessResponse()
    }

    func getProfileDetails(sessionManagementToken: String, username: String) async throws -> Data {
        await simulateNetwork()

        // 1. Get the user making the request
        guard let requestingUser = findUser(bySessionToken: sessionManagementToken) else {
            throw APIError.badServerResponse(statusCode: 401) // Unauthorized
        }
        
        // 2. Get the user whose profile is being viewed
        guard let profileUser = findUser(byUsername: username) else {
            throw APIError.badServerResponse(statusCode: 404) // Not Found
        }

        // 3. Calculate all statistics
        
        // Count posts where the authorId matches the profile user
        let postCount = posts.filter { $0.authorId == profileUser.id }.count
        
        // Count follows where 'userToId' matches the profile user
        let followerCount = userFollows.filter { $0.userToId == profileUser.id }.count
        
        // Count follows where 'userFromId' matches the profile user
        let followingCount = userFollows.filter { $0.userFromId == profileUser.id }.count
        
        // 4. Check if the requesting user is following the profile user
        let isFollowing = isUserFollowing(from: requestingUser.id, to: profileUser.id)
        let isBlocked = requestingUser.blocked.contains(profileUser.id)
        let isBlockedBy = requestingUser.blockedBy.contains(profileUser.id)

        // 5. Build the response data (matching the Swift struct)
        struct Fields: Codable {
            let username: String
            let post_count: Int
            let follower_count: Int
            let following_count: Int
            let is_following: Bool
            let is_blocked: Bool
            let identity_is_verified: Bool
            let is_adult: Bool
        }
        
        if isBlockedBy {
             let fields = Fields(
                username: profileUser.username,
                post_count: 0,
                follower_count: 0,
                following_count: 0,
                is_following: false,
                is_blocked: isBlocked,
                identity_is_verified: false,
                is_adult: false
            )
            return try createSerializedResponse(fields: fields)
        }
        
        let fields = Fields(
            username: profileUser.username,
            post_count: postCount,
            follower_count: followerCount,
            following_count: followingCount,
            is_following: isFollowing,
            is_blocked: isBlocked,
            identity_is_verified: profileUser.identityIsVerified,
            is_adult: profileUser.isAdult
        )

        // 6. Return the data using your existing helper
        return try createSerializedResponse(fields: fields)
    }

    // MARK: - Appeals

    private func hasAppeal(forTarget id: String) -> Bool {
        appeals.contains { $0.targetId == id }
    }

    func getHiddenPosts(sessionManagementToken: String, batch: Int) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 401) }

        // Pending posts have nothing to appeal yet and final rejections are
        // terminal, so neither belongs on the appeals screen (#282).
        let hidden = posts
            .filter { $0.authorId == user.id && $0.isHidden && isAppealable($0) }
            .sorted { $0.createdDate > $1.createdDate }

        let startIndex = batch * pageSize
        struct Fields: Codable {
            let post_identifier: String
            let image_url: String?
            let caption: String
            let hidden_reason: String
            let has_appeal: Bool
        }
        guard startIndex < hidden.count else { return try createSerializedListResponse(fieldsList: [Fields]()) }
        let endIndex = min(startIndex + pageSize, hidden.count)

        let fields = hidden[startIndex..<endIndex].map {
            Fields(post_identifier: $0.postIdentifier, image_url: $0.imageURL, caption: $0.caption,
                   hidden_reason: $0.hiddenReason, has_appeal: hasAppeal(forTarget: $0.postIdentifier))
        }
        return try createSerializedListResponse(fieldsList: fields)
    }

    func getHiddenComments(sessionManagementToken: String, batch: Int) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 401) }

        let hidden = comments
            .filter { $0.authorUsername == user.username && $0.isHidden }
            .sorted { $0.createdDate > $1.createdDate }

        let startIndex = batch * pageSize
        struct Fields: Codable {
            let comment_identifier: String
            let body: String
            let hidden_reason: String
            let has_appeal: Bool
        }
        guard startIndex < hidden.count else { return try createSerializedListResponse(fieldsList: [Fields]()) }
        let endIndex = min(startIndex + pageSize, hidden.count)

        let fields = hidden[startIndex..<endIndex].map {
            Fields(comment_identifier: $0.commentIdentifier, body: $0.body,
                   hidden_reason: $0.hiddenReason, has_appeal: hasAppeal(forTarget: $0.commentIdentifier))
        }
        return try createSerializedListResponse(fieldsList: fields)
    }

    func getMyAppeals(sessionManagementToken: String, batch: Int) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 401) }

        let mine = appeals
            .filter { $0.appellantId == user.id }
            .sorted { $0.createdDate > $1.createdDate }

        let startIndex = batch * pageSize
        struct Fields: Codable {
            let appeal_identifier: String
            let target_type: String?
            let status: String
            let reason: String
            let content_snapshot: String?
            let resolution_note: String?
        }
        guard startIndex < mine.count else { return try createSerializedListResponse(fieldsList: [Fields]()) }
        let endIndex = min(startIndex + pageSize, mine.count)

        let fields = mine[startIndex..<endIndex].map {
            Fields(appeal_identifier: $0.appealIdentifier, target_type: $0.targetType, status: $0.status,
                   reason: $0.reason, content_snapshot: $0.contentSnapshot, resolution_note: nil)
        }
        return try createSerializedListResponse(fieldsList: fields)
    }

    func submitAppeal(sessionManagementToken: String, targetType: String, targetIdentifier: String, reason: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 401) }

        let snapshot: String
        switch targetType {
        case "post":
            // Pending and final-rejected posts are not appealable (#282).
            guard let post = posts.first(where: { $0.postIdentifier == targetIdentifier && $0.authorId == user.id && $0.isHidden && isAppealable($0) }) else {
                throw APIError.serverError(statusCode: 400, serverMessage: "No appealable item with that identifier")
            }
            snapshot = post.caption
        case "comment":
            guard let comment = comments.first(where: { $0.commentIdentifier == targetIdentifier && $0.authorUsername == user.username && $0.isHidden }) else {
                throw APIError.serverError(statusCode: 400, serverMessage: "No appealable item with that identifier")
            }
            snapshot = comment.body
        default:
            // Match the backend, which rejects any target_type other than
            // post/comment instead of silently treating it as a comment.
            throw APIError.serverError(statusCode: 400, serverMessage: "Invalid target_type")
        }

        if hasAppeal(forTarget: targetIdentifier) {
            throw APIError.serverError(statusCode: 400, serverMessage: "This item has already been appealed")
        }

        let appeal = MockAppeal(appellantId: user.id, targetType: targetType, targetId: targetIdentifier,
                                reason: reason, contentSnapshot: snapshot)
        appeals.append(appeal)
        struct Fields: Codable { let appeal_identifier: String }
        return try createSerializedResponse(fields: Fields(appeal_identifier: appeal.appealIdentifier))
    }
}

