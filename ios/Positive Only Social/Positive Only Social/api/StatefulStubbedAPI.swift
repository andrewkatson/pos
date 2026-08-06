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
    // Sequential join number (issue #198), assigned in registration order.
    var membershipNumber: Int? = nil
    var blocked: [UUID] = []
    var blockedBy: [UUID] = []
    // Two-factor authentication (issue #348). A secret without the enabled
    // flag is a pending enrollment; recovery codes are removed as they are used.
    var totpSecret: String? = nil
    var totpEnabled: Bool = false
    var recoveryCodes: [String] = []
    // Profile photo (issue #7). `profileImageUrl` is the approved photo shown to
    // everyone; `pendingProfileImageUrl` is a photo still under (stubbed) review,
    // shown to nobody until approved. The stub has no classifier, so it approves
    // immediately — like the backend's eager (no-Redis) mode — leaving
    // `profileImageStatus` "approved" while the set response still reports
    // "pending".
    var profileImageUrl: String? = nil
    var pendingProfileImageUrl: String? = nil
    var profileImageStatus: String = "none"
    var profileImageReasonCode: String? = nil
    // Free-text bio (issue #380); "" when unset.
    var bio: String = ""
    // Positive interest tags (issues #446/#35): weighting buckets (picks ∪
    // mapped freeform) and the freeform terms the user typed.
    var interestCategories: [String] = []
    var freeformInterests: [String] = []
    // Google's `sub` claim once this account is linked to a Google identity
    // (issue #10); nil for password-only accounts.
    var googleSub: String? = nil

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
    // Relationship category the follower assigned (issue #392).
    var category: String = FollowCategory.following.rawValue
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
    // Whole-caption font + whole-tile background color keys (issue #318).
    var captionFont: String = "default"
    var backgroundColor: String = "default"
    var likes: [String] = [] // Usernames of likers
    var savers: [String] = [] // Usernames who saved the post (issue #193/#412)
    var reports: [(username: String, reason: String)] = []
    var commentThreads: [MockCommentThread] = []
    var isHidden: Bool = false
    var hiddenReason: String = GVOAppConstants.emptyString
    /// Public reason code recorded by the (stubbed) async classifier (#282).
    var reasonCode: String? = nil
    /// Who may see the post (issue #392).
    var audience: String = PostAudience.public.rawValue
    /// Hashtags parsed from the caption (issue #379), normalized and sorted.
    var tags: [String] = []
    let createdDate = Date()
}

/// One post as the three listing endpoints (feed, following feed, user posts)
/// serialize it. Each row carries the same like/report state `getPostDetails`
/// returns so the clients can act on a post straight from a list (issue #267).
fileprivate struct PostListingFields: Codable {
    let post_identifier: String
    let image_url: String?
    let caption: String
    let caption_font: String
    let background_color: String
    let author_username: String
    /// The post author's approved profile photo (issue #7), or nil. Compressed
    /// and original point at the same stub URL, mirroring the backend fields.
    let author_profile_image_url: String?
    let author_profile_image_original_url: String?
    let post_likes: Int
    let is_liked: Bool
    /// Whether the viewer has saved this post (issue #193/#412).
    let is_saved: Bool
    let is_reported: Bool
    let report_reason: String?
    /// Comments visible to the viewer, and when the post was made — the extra
    /// context the feed rows show (issue #249).
    let comment_count: Int
    //TODO: eBlender rename to camelCase creationTime (via CodingKeys).
    let creation_time: String?
    /// Author-only classification state (#282), mirroring the backend: only a
    /// viewer's own grid carries these. Encoded as nil (and so omitted) for
    /// everyone else's posts and for the feeds.
    let status: String?
    let hidden: Bool?
    let hidden_reason: String?
    let appealable: Bool?
    /// Who may see the post (issue #392).
    let audience: String?
    /// Hashtags parsed from the caption (issue #379).
    let tags: [String]
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
    /// Inline formatting spans over `body` (issue #318); nil = plain.
    var bodyFormatting: [CommentFormatSpan]? = nil
    /// Who may see this comment (issue #445).
    var audience: String = PostAudience.public.rawValue
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

    // Monotonic source for membership numbers (issue #198). A dedicated counter
    // rather than users.count so a delete + re-register never reuses a number,
    // matching the backend's "creation order, never reused" behavior.
    private var membershipCounter = 0

    // Usernames pre-seeded from the launch environment (issue #377). UI tests
    // seed the accounts they use so a test can log in directly instead of
    // walking the whole registration UI first. `register` is idempotent for
    // these names (see below) so a test that *does* exercise the register form
    // on a seeded account still succeeds instead of hitting "already exists".
    private var seededUsernames: Set<String> = []

    init() {
        seedUsersFromEnvironment()
    }

    /// Seeds verified accounts listed in the `seed-usernames` launch
    /// environment variable (issue #377): names joined by `;`. Every seeded
    /// account shares the sign-in value from `seed-secret`, so the two are
    /// passed separately rather than as colon-joined pairs — pairing them
    /// reads like an embedded credential to secret scanners, and this is
    /// simpler anyway. The email is derived as `<username>@test.com`, matching
    /// the convention every UI test uses. Both variables must be set together;
    /// usernames without a sign-in value seed nothing and log why.
    ///
    /// Nothing here is sensitive: `StatefulStubbedAPI` is an in-memory fake
    /// used only under UI testing, and the value arrives at runtime from the
    /// test harness rather than being compiled in.
    private func seedUsersFromEnvironment() {
        guard isUITesting(),
              let raw = ProcessInfo.processInfo.environment["seed-usernames"],
              !raw.isEmpty else { return }
        // Seeding accounts with an empty sign-in value would create accounts
        // that can never be logged into, and the test would then fail deep in a
        // login flow with nothing pointing back at the real cause. Refuse to
        // seed and say why, so the misconfiguration explains itself.
        guard let sharedSignIn = ProcessInfo.processInfo.environment["seed-secret"],
              !sharedSignIn.isEmpty else {
            NSLog("%@", "[seed] 'seed-usernames' was set but 'seed-secret' is missing or empty, "
                  + "so no accounts were seeded. Every seeded-account sign-in would have failed. "
                  + "Set both launch environment variables together.")
            return
        }
        for entry in raw.split(separator: ";") {
            let username = String(entry)
            if username.isEmpty { continue }
            if findUser(byUsername: username) != nil { continue }
            var user = MockUser(username: username, email: "\(username)@test.com", passwordHash: sharedSignIn)
            membershipCounter += 1
            user.membershipNumber = membershipCounter
            user.emailVerified = true
            users.append(user)
            seededUsernames.insert(username)
        }
    }

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

    /// Serializes one post for a listing endpoint, including the viewer's own
    /// like/report state so the list can offer the same actions the post detail
    /// view does (issue #267).
    fileprivate func postListingFields(
        for post: MockPost,
        viewer: MockUser,
        isOwnGrid: Bool = false
    ) -> PostListingFields {
        let viewerReport = post.reports.first(where: { $0.username == viewer.username })
        let authorAvatar = approvedAvatarUrl(forUserId: post.authorId)
        return PostListingFields(
            post_identifier: post.postIdentifier,
            image_url: post.imageURL,
            caption: post.caption,
            caption_font: post.captionFont,
            background_color: post.backgroundColor,
            author_username: users.first(where: { $0.id == post.authorId })?.username ?? "Unknown User",
            author_profile_image_url: authorAvatar,
            author_profile_image_original_url: authorAvatar,
            post_likes: post.likes.count,
            is_liked: post.likes.contains(viewer.username),
            is_saved: post.savers.contains(viewer.username),
            is_reported: viewerReport != nil,
            report_reason: viewerReport?.reason,
            comment_count: commentCount(forPost: post.postIdentifier),
            // Mirror Django's DjangoJSONEncoder, which emits a colon-separated
            // UTC offset with fractional seconds (e.g. "…+00:00"), not a "Z"
            // suffix, so the client's date parsing is exercised against the
            // real backend format.
            creation_time: post.createdDate.formatted(
                Date.ISO8601FormatStyle().year().month().day()
                    .time(includingFractionalSeconds: true)
                    .timeZone(separator: .colon)
            ),
            status: isOwnGrid ? classificationStatus(post) : nil,
            hidden: isOwnGrid ? post.isHidden : nil,
            hidden_reason: isOwnGrid ? post.hiddenReason : nil,
            appealable: isOwnGrid ? isAppealable(post) : nil,
            audience: post.audience,
            tags: post.tags
        )
    }

    /// Mirrors visibility._audience_allows (issue #392): whether the post's
    /// audience admits `viewer`. Public admits everyone and the author always
    /// sees their own posts; otherwise the author must have labeled the viewer
    /// with a category close enough for the audience's nested tier.
    fileprivate func audienceAdmits(_ post: MockPost, viewer: MockUser) -> Bool {
        if post.audience == PostAudience.public.rawValue || post.authorId == viewer.id {
            return true
        }
        guard let follow = userFollows.first(where: {
            $0.userFromId == post.authorId && $0.userToId == viewer.id
        }), let category = FollowCategory(rawValue: follow.category),
            let audience = PostAudience(rawValue: post.audience) else {
            return false
        }
        let rank: [FollowCategory: Int] = [.following: 1, .friend: 2, .family: 3]
        let required: [PostAudience: Int] = [.following: 1, .friends: 2, .family: 3]
        return (rank[category] ?? 0) >= (required[audience] ?? 0)
    }

    /// Comment mirror of `audienceAdmits` (issue #445): whether the comment's
    /// audience admits `viewer`. Resolves the author by username since comments
    /// carry a username rather than an id.
    fileprivate func audienceAdmits(comment: MockComment, viewer: MockUser) -> Bool {
        if comment.audience == PostAudience.public.rawValue || comment.authorUsername == viewer.username {
            return true
        }
        guard let author = users.first(where: { $0.username == comment.authorUsername }),
              let follow = userFollows.first(where: {
                  $0.userFromId == author.id && $0.userToId == viewer.id
              }), let category = FollowCategory(rawValue: follow.category),
              let audience = PostAudience(rawValue: comment.audience) else {
            return false
        }
        let rank: [FollowCategory: Int] = [.following: 1, .friend: 2, .family: 3]
        let required: [PostAudience: Int] = [.following: 1, .friends: 2, .family: 3]
        return (rank[category] ?? 0) >= (required[audience] ?? 0)
    }

    /// The followed-feed toggle applied to a comment author (issue #445):
    /// whether `viewer` labeled the comment's author with exactly `category`. A
    /// plain follow counts as `.following`; the viewer's own comments never
    /// match (you do not follow yourself).
    fileprivate func commentMatchesCategory(_ comment: MockComment, viewer: MockUser, category: FollowCategory) -> Bool {
        guard let author = users.first(where: { $0.username == comment.authorUsername }),
              let follow = userFollows.first(where: {
                  $0.userFromId == viewer.id && $0.userToId == author.id
              }) else {
            return false
        }
        return (FollowCategory(rawValue: follow.category) ?? .following) == category
    }

    /// Comments in a thread the `viewer` may see (issue #445): not hidden
    /// (unless their own), audience-admitted, and — when `category` is set — by
    /// an author the viewer labeled with exactly that category.
    fileprivate func visibleComments(inThread threadId: String, viewer: MockUser, category: FollowCategory?) -> [MockComment] {
        comments.filter { comment in
            guard comment.threadId == threadId else { return false }
            let isOwn = comment.authorUsername == viewer.username
            if let category = category {
                // The exact-category toggle drops your own comments.
                return !isOwn && !comment.isHidden
                    && audienceAdmits(comment: comment, viewer: viewer)
                    && commentMatchesCategory(comment, viewer: viewer, category: category)
            }
            if isOwn { return true }
            return !comment.isHidden && audienceAdmits(comment: comment, viewer: viewer)
        }
    }

    /// Parses #hashtags from a caption the same way the backend does (issue
    /// #379): a '#' followed by unicode letters, numbers, or underscore
    /// (\p{L}\p{N}_) — exactly equivalent to the backend's Python `\w` on a
    /// `str`. Lowercased (locale-independent, like str.lower()), de-duped,
    /// length- and count-capped (matching MAX_TAG_LENGTH / MAX_TAGS_PER_POST),
    /// and returned sorted to match the backend's serialization.
    fileprivate static func extractTags(from caption: String) -> [String] {
        guard let regex = try? NSRegularExpression(pattern: "#([\\p{L}\\p{N}_]+)") else { return [] }
        let range = NSRange(caption.startIndex..., in: caption)
        var seen = Set<String>()
        var names: [String] = []
        regex.enumerateMatches(in: caption, range: range) { match, _, _ in
            guard let match, let r = Range(match.range(at: 1), in: caption) else { return }
            let name = caption[r].lowercased()
            if name.count <= 100 && names.count < 30 && !seen.contains(name) {
                seen.insert(name)
                names.append(name)
            }
        }
        return names.sorted()
    }

    /// The number of visible comments on a post, across all of its threads.
    private func commentCount(forPost postIdentifier: String) -> Int {
        let threadIdentifiers = Set(
            commentThreads.filter { $0.postId == postIdentifier }.map { $0.commentThreadIdentifier }
        )
        return comments.filter { threadIdentifiers.contains($0.threadId) && !$0.isHidden }.count
    }

    /// An author's approved profile photo (issue #7), or nil — only an approved
    /// photo is ever exposed to others, mirroring the backend. The compressed and
    /// original variants point at the same stub URL.
    private func approvedAvatarUrl(forUserId id: UUID) -> String? {
        guard let user = users.first(where: { $0.id == id }) else { return nil }
        return user.profileImageStatus == "approved" ? user.profileImageUrl : nil
    }

    private func approvedAvatarUrl(forUsername name: String) -> String? {
        guard let user = users.first(where: { $0.username == name }) else { return nil }
        return user.profileImageStatus == "approved" ? user.profileImageUrl : nil
    }

    private func createEmptySuccessResponse() throws -> Data {
        return try JSONEncoder().encode(["message": "ok"])
    }
    private func simulateNetwork() async { try? await Task.sleep(for: .seconds(simulatedLatency)) }
    private func generateToken() -> String { UUID().uuidString.replacingOccurrences(of: "-", with: "") }

    // MARK: - Implementations
    
    func register(username: String, email: String, password: String, rememberMe: String, ip: String, dateOfBirth: String, interestCategories: [String], interestFreeform: [String]) async throws -> Data {
        await simulateNetwork()
        // A pre-seeded account (issue #377) is not a real prior registration —
        // it stands in for one the test skipped walking through the UI. Let the
        // first register call for such a name adopt the seeded row instead of
        // failing as a duplicate, then drop it from the seeded set so a genuine
        // second registration still gets the "already exists" rejection.
        // Consume the marker up front, whichever path this call takes. Removing
        // it only inside the adoption branch left it set when the seeded row had
        // already been deleted — the name would then register for real, still be
        // flagged as seeded, and a later duplicate registration would adopt that
        // real account instead of being rejected.
        let wasSeeded = seededUsernames.remove(username) != nil
        if wasSeeded,
           let index = users.firstIndex(where: { $0.username == username }) {
            users[index].email = email
            users[index].passwordHash = password
            let membershipNumber = users[index].membershipNumber
            let userId = users[index].id
            sessions.removeAll { $0.userId == userId }
            let seededSession = MockSession(managementToken: generateToken(), userId: userId, ip: ip)
            sessions.append(seededSession)
            if Bool(rememberMe.lowercased()) ?? false {
                let cookie = MockLoginCookie(seriesIdentifier: UUID().uuidString, token: generateToken(), userId: userId)
                loginCookies.append(cookie)
                struct Fields: Codable { let series_identifier, login_cookie_token, session_management_token, user_id: String; let membership_number: Int? }
                return try createSerializedResponse(fields: Fields(
                    series_identifier: cookie.seriesIdentifier,
                    login_cookie_token: cookie.token,
                    session_management_token: seededSession.managementToken,
                    user_id: userId.uuidString,
                    membership_number: membershipNumber
                ))
            }
            struct Fields: Codable { let session_management_token, user_id: String; let membership_number: Int? }
            return try createSerializedResponse(fields: Fields(
                session_management_token: seededSession.managementToken,
                user_id: userId.uuidString,
                membership_number: membershipNumber
            ))
        }
        if findUser(byUsername: username) != nil || findUser(byEmail: email) != nil {
            throw APIError.badServerResponse(statusCode: 400) // "User already exists"
        }
        var newUser = MockUser(username: username, email: email, passwordHash: password)
        // Assign the next sequential membership number (issue #198), mirroring
        // the backend which numbers accounts in creation order and never reuses
        // a number even after a delete.
        membershipCounter += 1
        newUser.membershipNumber = membershipCounter
        let membershipNumber = newUser.membershipNumber
        users.append(newUser)

        // Interests picked during sign-up ride along in the register payload
        // (issues #446/#35). Best-effort, exactly like the backend.
        if !interestCategories.isEmpty || !interestFreeform.isEmpty,
           let index = users.firstIndex(where: { $0.id == newUser.id }) {
            _ = applyInterests(atIndex: index, categories: interestCategories, freeform: interestFreeform)
        }
        let newSession = MockSession(managementToken: generateToken(), userId: newUser.id, ip: ip)
        sessions.append(newSession)

        let wantsRememberMe = Bool(rememberMe.lowercased()) ?? false
        if wantsRememberMe {
            let cookie = MockLoginCookie(seriesIdentifier: UUID().uuidString, token: generateToken(), userId: newUser.id)
            loginCookies.append(cookie)
            struct Fields: Codable { let series_identifier, login_cookie_token, session_management_token, user_id: String; let membership_number: Int? }
            return try createSerializedResponse(fields: Fields(
                series_identifier: cookie.seriesIdentifier,
                login_cookie_token: cookie.token,
                session_management_token: newSession.managementToken,
                user_id: newUser.id.uuidString,
                membership_number: membershipNumber
            ))
        } else {
            struct Fields: Codable { let session_management_token, user_id: String; let membership_number: Int? }
            return try createSerializedResponse(fields: Fields(session_management_token: newSession.managementToken, user_id: newUser.id.uuidString, membership_number: membershipNumber))
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

    func loginWithGoogle(idToken: String, rememberMe: String, ip: String) async throws -> Data {
        await simulateNetwork()

        // The real backend verifies the token against Google's public keys; the
        // stub has neither a network nor the keys, so it reads the claims
        // straight out of the payload segment (see google_auth.py for what the
        // real check does).
        guard let claims = Self.decodeIdTokenClaims(idToken),
              let sub = claims.sub, let rawEmail = claims.email else {
            throw APIError.serverError(statusCode: 401, serverMessage: "invalid_google_token")
        }
        // Verified has to be asserted, not merely not-denied: the backend
        // requires `email_verified is True`, so a missing claim counts as
        // unverified there and must here too, or the stub is more permissive
        // than production.
        if claims.email_verified != true {
            throw APIError.serverError(statusCode: 403, serverMessage: "google_email_unverified")
        }
        let email = rawEmail.lowercased()

        var createdAccount = false
        var index = users.firstIndex { $0.googleSub == sub }
        if index == nil {
            // Google has verified the address, so an account already holding it
            // is the same person: link rather than making a second account.
            if let existing = users.firstIndex(where: { $0.email.lowercased() == email }) {
                users[existing].googleSub = sub
                users[existing].emailVerified = true
                users[existing].emailVerificationToken = nil
                index = existing
            }
        }
        if index == nil {
            // Usernames need at least 10 word characters, so a short local part
            // is padded — mirroring _google_username_base in the backend.
            let localPart = String(email.split(separator: "@").first ?? "")
            let base = localPart.filter { $0.isLetter || $0.isNumber || $0 == "_" }
            let stem = base.isEmpty ? "friend" : base
            var username = stem.count >= 10 ? stem : stem + String(repeating: "0", count: 10 - stem.count)
            var suffix = 1
            while findUser(byUsername: username) != nil {
                username = stem + String(format: "%04d", suffix)
                suffix += 1
            }

            // No password exists behind a Google account. The stub compares
            // passwords as plain strings, so this is a value nobody could type
            // rather than a readable placeholder somebody might.
            var newUser = MockUser(username: username, email: email, passwordHash: "no-password-\(UUID().uuidString)")
            newUser.googleSub = sub
            membershipCounter += 1
            newUser.membershipNumber = membershipCounter
            users.append(newUser)
            index = users.count - 1
            createdAccount = true
        }

        guard let userIndex = index else {
            throw APIError.serverError(statusCode: 500, serverMessage: "Could not create an account")
        }
        let user = users[userIndex]

        // Holding the Google account is a first factor, not a bypass of the second.
        if user.totpEnabled {
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

        struct Fields: Codable {
            let session_management_token, username, user_id: String
            let series_identifier, login_cookie_token: String?
            let created_account: Bool
            let membership_number: Int?
        }
        var seriesIdentifier: String? = nil
        var loginCookieToken: String? = nil
        if Bool(rememberMe.lowercased()) ?? false {
            let cookie = MockLoginCookie(seriesIdentifier: UUID().uuidString, token: generateToken(), userId: user.id)
            loginCookies.append(cookie)
            seriesIdentifier = cookie.seriesIdentifier
            loginCookieToken = cookie.token
        }
        return try createSerializedResponse(fields: Fields(
            session_management_token: newSession.managementToken,
            username: user.username,
            user_id: user.id.uuidString,
            series_identifier: seriesIdentifier,
            login_cookie_token: loginCookieToken,
            created_account: createdAccount,
            membership_number: createdAccount ? user.membershipNumber : nil
        ))
    }

    /// The claims the stub reads out of an unverified ID token payload.
    struct StubGoogleClaims: Decodable {
        let sub: String?
        let email: String?
        let email_verified: Bool?
    }

    static func decodeIdTokenClaims(_ idToken: String) -> StubGoogleClaims? {
        let segments = idToken.split(separator: ".", omittingEmptySubsequences: false)
        guard segments.count == 3 else { return nil }
        var payload = String(segments[1])
            .replacingOccurrences(of: "-", with: "+")
            .replacingOccurrences(of: "_", with: "/")
        // base64url drops the padding that Data(base64Encoded:) insists on.
        while payload.count % 4 != 0 { payload += "=" }
        guard let data = Data(base64Encoded: payload) else { return nil }
        return try? JSONDecoder().decode(StubGoogleClaims.self, from: data)
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
            throw APIError.serverError(statusCode: 400, serverMessage: GVOAppConstants.invalidTwoFactorChallengeError)
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

    func confirmTotp(sessionManagementToken: String, password: String, totpCode: String) async throws -> Data {
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
        guard users[userIndex].passwordHash == password else {
            throw APIError.serverError(statusCode: 400, serverMessage: "Invalid password")
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

    func getCurrentUser(sessionManagementToken: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 401) }
        struct Fields: Codable { let username, email: String }
        return try createSerializedResponse(fields: Fields(username: user.username, email: user.email))
    }

    func changePassword(sessionManagementToken: String, currentPassword: String, newPassword: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken),
              let userIndex = users.firstIndex(where: { $0.id == user.id })
        else { throw APIError.badServerResponse(statusCode: 401) }
        // Field validation first, mirroring the backend: the new password must
        // meet the registration strength policy (Patterns.password) before the
        // current password is checked, so a weak password fails here exactly as
        // it would in production rather than silently succeeding against the stub.
        let strongPassword = "^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=\\S+$).{8,}$"
        guard newPassword.range(of: strongPassword, options: .regularExpression) != nil else {
            throw APIError.serverError(statusCode: 400, serverMessage: "Invalid fields ['NEW_PASSWORD']")
        }
        // The current password is required as well as the session: a stolen
        // session alone must not be enough to lock the real owner out.
        guard users[userIndex].passwordHash == currentPassword else {
            throw APIError.serverError(statusCode: 400, serverMessage: "Invalid password")
        }
        guard newPassword != currentPassword else {
            throw APIError.serverError(statusCode: 400, serverMessage: "New password must be different from the current password")
        }
        users[userIndex].passwordHash = newPassword
        // Mirror the backend: a password change evicts every *other* session and
        // all remember-me cookies, keeping only the caller's current session so
        // they aren't logged out of the device they just used.
        sessions.removeAll { $0.userId == user.id && $0.managementToken != sessionManagementToken }
        loginCookies.removeAll { $0.userId == user.id }
        struct Fields: Codable { let message: String }
        return try createSerializedResponse(fields: Fields(message: "Password changed successfully"))
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

    func makePost(sessionManagementToken: String, imageURL: String?, caption: String, audience: String? = nil, captionFont: String = "default", backgroundColor: String = "default") async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        // Stub pre-filter, mirroring the backend's cheap inline check (#282): a
        // blatant hit is rejected immediately and the post is never created.
        if caption.contains("negative") {
            throw APIError.serverError(statusCode: 400, serverMessage: "Text is not positive because your caption did not meet our positivity guidelines. This decision is final and cannot be appealed.")
        }
        var newPost = MockPost(authorId: user.id, imageURL: imageURL, caption: caption)
        newPost.captionFont = captionFont
        newPost.backgroundColor = backgroundColor
        newPost.isHidden = true
        newPost.hiddenReason = "pending_classification"
        // Nil / unknown audience falls back to public, matching the backend (#392).
        newPost.audience = PostAudience(rawValue: audience ?? "").map { $0.rawValue } ?? PostAudience.public.rawValue
        newPost.tags = Self.extractTags(from: caption)
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

    func savePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        await simulateNetwork()
        guard let saver = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let postIndex = posts.firstIndex(where: { $0.postIdentifier == postIdentifier }) else { throw APIError.badServerResponse(statusCode: 400) }
        // Mirror the backend (save_post): a repeat save is rejected with 400
        // ("Already saved post"), like a double-like — so the client's optimistic
        // revert path is exercised. Saving your own post is still allowed.
        if posts[postIndex].savers.contains(saver.username) { throw APIError.badServerResponse(statusCode: 400) }
        posts[postIndex].savers.append(saver.username)
        return try createEmptySuccessResponse()
    }

    func unsavePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        await simulateNetwork()
        guard let saver = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let postIndex = posts.firstIndex(where: { $0.postIdentifier == postIdentifier }) else { throw APIError.badServerResponse(statusCode: 400) }
        // Mirror the backend (unsave_post): unsaving a post that wasn't saved is
        // rejected with 400 ("Post not saved yet").
        guard let saveIndex = posts[postIndex].savers.firstIndex(of: saver.username) else { throw APIError.badServerResponse(statusCode: 400) }
        posts[postIndex].savers.remove(at: saveIndex)
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
                !user.blockedBy.contains(post.authorId) &&
                audienceAdmits(post, viewer: user)
            }
            .sorted { $0.createdDate > $1.createdDate }

        let startIndex = batch * pageSize

        // Check if the requested page is beyond the available posts
        guard startIndex < relevantPosts.count else {
            // Return an empty list, NOT an error
            return try createSerializedListResponse(fieldsList: [PostListingFields]())
        }

        let endIndex = min(startIndex + pageSize, relevantPosts.count)
        let paginatedPosts = Array(relevantPosts[startIndex..<endIndex])

        let fieldObjects = paginatedPosts.map { postListingFields(for: $0, viewer: user) }

        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func getPostsForFollowedUsers(sessionManagementToken: String, batch: Int, category: String? = nil) async throws -> Data {
        getPostsForFollowedUsersCallCount+=1
        await simulateNetwork()

        // 1. Authenticate the user
        guard let currentUser = findUser(bySessionToken: sessionManagementToken) else {
            throw APIError.badServerResponse(statusCode: 401) // Unauthorized
        }

        // 2. Find all user IDs that the current user follows, optionally
        //    narrowed to one exact relationship category (issue #392).
        let followedUserIDs = userFollows
            .filter { $0.userFromId == currentUser.id && (category == nil || $0.category == category) }
            .map { $0.userToId }

        // 3. Get all posts from those users, filtering out hidden posts
        let relevantPosts = posts
            .filter { post in
                // Post author is in the followed list AND post is not hidden
                followedUserIDs.contains(post.authorId) &&
                !post.isHidden &&
                !currentUser.blocked.contains(post.authorId) &&
                !currentUser.blockedBy.contains(post.authorId) &&
                audienceAdmits(post, viewer: currentUser)
            }
            .sorted { $0.createdDate > $1.createdDate } // Sort by newest first
        
        let startIndex = batch * pageSize
        
        // Check if the requested page is beyond the available posts
        guard startIndex < relevantPosts.count else {
            // Return an empty list, NOT an error
            return try createSerializedListResponse(fieldsList: [PostListingFields]())
        }
        
        let endIndex = min(startIndex + pageSize, relevantPosts.count)
        let paginatedPosts = Array(relevantPosts[startIndex..<endIndex])

        // 5. Format the response (matching getPostsInFeed)
        let fieldObjects = paginatedPosts.map { postListingFields(for: $0, viewer: currentUser) }

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
             return try createSerializedListResponse(fieldsList: [PostListingFields]())
        }

        // Mirrors the backend's visible_posts: authors see their own hidden
        // posts (pending, appealable, report-hidden) in their grid; everyone
        // else only sees live ones. Final-rejection tombstones are visible to
        // nobody (#282).
        let isOwnGrid = user.id == targetUser.id
        let relevantPosts = posts
            .filter { $0.authorId == targetUser.id && $0.hiddenReason != "classifier_final" }
            .filter { isOwnGrid || !$0.isHidden }
            .filter { isOwnGrid || audienceAdmits($0, viewer: user) }
            .sorted { $0.createdDate > $1.createdDate } // Sort newest first

        let startIndex = batch * pageSize
        guard startIndex < relevantPosts.count else {
            // Return an empty list, NOT an error
            return try createSerializedListResponse(fieldsList: [PostListingFields]())
        }

        let endIndex = min(startIndex + pageSize, relevantPosts.count)
        let paginatedPosts = Array(relevantPosts[startIndex..<endIndex])

        // Author-only classification fields (#282) are included when viewing
        // one's own grid, mirroring the backend payload.
        let fieldObjects = paginatedPosts.map {
            postListingFields(for: $0, viewer: user, isOwnGrid: isOwnGrid)
        }

        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func getPostDetails(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 401) }
        guard let post = findPost(byIdentifier: postIdentifier) else { throw APIError.badServerResponse(statusCode: 400) }
        // Mirror can_view_post: a restricted post the viewer isn't in the
        // audience for reads exactly like a missing one (issue #392).
        if post.authorId != user.id && !audienceAdmits(post, viewer: user) {
            throw APIError.badServerResponse(statusCode: 400)
        }
        struct Fields: Codable {
            let post_identifier: String
            let image_url: String?
            let caption: String
            let caption_font: String
            let background_color: String
            //TODO: eBlender rename to camelCase creationTime (via CodingKeys).
            let creation_time: String
            let post_likes: Int
            let is_liked: Bool
            let is_saved: Bool
            let is_reported: Bool
            let report_reason: String?
            let author_username: String
            let audience: String?
            let tags: [String]
            let author_profile_image_url: String?
            let author_profile_image_original_url: String?
        }
        let userReport = post.reports.first(where: { $0.username == user.username })
        let authorAvatar = approvedAvatarUrl(forUserId: post.authorId)
        let fields = Fields(
            post_identifier: post.postIdentifier,
            image_url: post.imageURL,
            caption: post.caption,
            caption_font: post.captionFont,
            background_color: post.backgroundColor,
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
            is_saved: post.savers.contains(user.username),
            is_reported: userReport != nil,
            report_reason: userReport?.reason,
            author_username: users.first(where: {$0.id == post.authorId})?.username ?? "Unknown User",
            audience: post.audience,
            tags: post.tags,
            author_profile_image_url: authorAvatar,
            author_profile_image_original_url: authorAvatar
        )
        return try createSerializedResponse(fields: fields)
    }

    func getPostsForTag(sessionManagementToken: String, tag: String, batch: Int) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else {
            throw APIError.badServerResponse(statusCode: 401)
        }
        let normalized = tag.lowercased()
        // Same visibility + block rules as the other feeds: the viewer sees a
        // non-hidden post (or their own), from an author neither party blocked,
        // that carries this tag. Newest first (#379).
        let relevantPosts = posts
            .filter { $0.tags.contains(normalized) }
            .filter { $0.hiddenReason != "classifier_final" }
            .filter { $0.authorId == user.id || !$0.isHidden }
            .filter { !user.blocked.contains($0.authorId) && !user.blockedBy.contains($0.authorId) }
            .sorted { $0.createdDate > $1.createdDate }

        let startIndex = batch * pageSize
        guard startIndex < relevantPosts.count else {
            return try createSerializedListResponse(fieldsList: [PostListingFields]())
        }
        let endIndex = min(startIndex + pageSize, relevantPosts.count)
        let paginatedPosts = Array(relevantPosts[startIndex..<endIndex])
        let fieldObjects = paginatedPosts.map {
            postListingFields(for: $0, viewer: user, isOwnGrid: $0.authorId == user.id)
        }
        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func commentOnPost(sessionManagementToken: String, postIdentifier: String, commentText: String, formatting: [CommentFormatSpan]? = nil, audience: String? = nil) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard findPost(byIdentifier: postIdentifier) != nil else { throw APIError.badServerResponse(statusCode: 400) }

        var newThread = MockCommentThread(postId: postIdentifier)
        var newComment = MockComment(threadId: newThread.commentThreadIdentifier, authorUsername: user.username, body: commentText)
        newComment.bodyFormatting = formatting
        newComment.audience = audience ?? PostAudience.public.rawValue
        newThread.comments.append(newComment)
        
        comments.append(newComment)
        commentThreads.append(newThread)
        
        struct Fields: Codable { let comment_thread_identifier, comment_identifier: String }
        let fields = Fields(comment_thread_identifier: newThread.commentThreadIdentifier, comment_identifier: newComment.commentIdentifier)
        return try createSerializedResponse(fields: fields)
    }

    func replyToCommentThread(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentText: String, formatting: [CommentFormatSpan]? = nil, audience: String? = nil) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        guard let threadIndex = commentThreads.firstIndex(where: { $0.commentThreadIdentifier == commentThreadIdentifier }) else { throw APIError.badServerResponse(statusCode: 400) }

        var newComment = MockComment(threadId: commentThreadIdentifier, authorUsername: user.username, body: commentText)
        newComment.bodyFormatting = formatting
        newComment.audience = audience ?? PostAudience.public.rawValue
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

    func getCommentsForPost(sessionManagementToken: String, postIdentifier: String, batch: Int, category: String? = nil) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 401) }
        let categoryFilter = category.flatMap { FollowCategory(rawValue: $0) }
        // Only threads with a comment the viewer may see under the current filter
        // survive (issue #445), mirroring visible_comment_threads.
        let relevantThreads = commentThreads.filter {
            $0.postId == postIdentifier
                && !visibleComments(inThread: $0.commentThreadIdentifier, viewer: user, category: categoryFilter).isEmpty
        }

        // If there are no threads return gracefully
        if relevantThreads.isEmpty {
            return try createSerializedListResponse(fieldsList: [Fields]())
        }

        struct Fields: Codable { let comment_thread_identifier: String }
        let fieldObjects = relevantThreads.map { Fields(comment_thread_identifier: $0.commentThreadIdentifier) }
        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func getCommentsForThread(sessionManagementToken: String, commentThreadIdentifier: String, batch: Int, category: String? = nil) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 401) }
        let categoryFilter = category.flatMap { FollowCategory(rawValue: $0) }
        let relevantComments = visibleComments(inThread: commentThreadIdentifier, viewer: user, category: categoryFilter)
            .sorted { $0.createdDate < $1.createdDate }

        if relevantComments.isEmpty {
            // If there are no comments return gracefully
            return try createSerializedListResponse(fieldsList: [Fields]())
        }

        struct Fields: Codable {
            let comment_identifier, body, author_username: String
            let author_profile_image_url: String?
            let author_profile_image_original_url: String?
            let body_formatting: [CommentFormatSpan]?
            let audience: String
            let creation_time, updated_time: String
            let comment_likes: Int
            let is_liked: Bool
            let is_reported: Bool
            let report_reason: String?
        }

        let dateFormatter = ISO8601DateFormatter()
        let fieldObjects = relevantComments.map { comment in
            let userReport = comment.reports.first(where: { $0.username == user.username })
            let authorAvatar = approvedAvatarUrl(forUsername: comment.authorUsername)
            return Fields(comment_identifier: comment.commentIdentifier, body: comment.body, author_username: comment.authorUsername,
                   author_profile_image_url: authorAvatar,
                   author_profile_image_original_url: authorAvatar,
                   body_formatting: comment.bodyFormatting,
                   audience: comment.audience,
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
        
        struct Fields: Codable {
            let username: String
            let identity_is_verified: Bool
            let author_profile_image_url: String?
            let author_profile_image_original_url: String?
        }
        let fieldObjects = matchingUsers.map { user -> Fields in
            let avatar = user.profileImageStatus == "approved" ? user.profileImageUrl : nil
            return Fields(username: user.username, identity_is_verified: user.identityIsVerified,
                          author_profile_image_url: avatar, author_profile_image_original_url: avatar)
        }
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

        struct Fields: Codable {
            let username: String
            let identity_is_verified: Bool
            let author_profile_image_url: String?
            let author_profile_image_original_url: String?
        }
        let fieldObjects = blockedUsers.map { user -> Fields in
            let avatar = user.profileImageStatus == "approved" ? user.profileImageUrl : nil
            return Fields(username: user.username, identity_is_verified: user.identityIsVerified,
                          author_profile_image_url: avatar, author_profile_image_original_url: avatar)
        }
        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func getFollowers(sessionManagementToken: String) async throws -> Data {
        await simulateNetwork()
        guard let currentUser = findUser(bySessionToken: sessionManagementToken) else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        // Followers are the userFrom sides of follows pointing at the current user.
        let followerIds = Set(userFollows.filter { $0.userToId == currentUser.id }.map { $0.userFromId })
        let followers = users
            .filter { followerIds.contains($0.id) }
            .sorted { $0.username < $1.username }

        struct Fields: Codable {
            let username: String
            let identity_is_verified: Bool
            let author_profile_image_url: String?
            let author_profile_image_original_url: String?
        }
        let fieldObjects = followers.map { user -> Fields in
            let avatar = user.profileImageStatus == "approved" ? user.profileImageUrl : nil
            return Fields(username: user.username, identity_is_verified: user.identityIsVerified,
                          author_profile_image_url: avatar, author_profile_image_original_url: avatar)
        }
        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func getFollowing(sessionManagementToken: String) async throws -> Data {
        await simulateNetwork()
        guard let currentUser = findUser(bySessionToken: sessionManagementToken) else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        // Following are the userTo sides of follows originating from the current user.
        let followingIds = Set(userFollows.filter { $0.userFromId == currentUser.id }.map { $0.userToId })
        let following = users
            .filter { followingIds.contains($0.id) }
            .sorted { $0.username < $1.username }

        struct Fields: Codable {
            let username: String
            let identity_is_verified: Bool
            let author_profile_image_url: String?
            let author_profile_image_original_url: String?
        }
        let fieldObjects = following.map { user -> Fields in
            let avatar = user.profileImageStatus == "approved" ? user.profileImageUrl : nil
            return Fields(username: user.username, identity_is_verified: user.identityIsVerified,
                          author_profile_image_url: avatar, author_profile_image_original_url: avatar)
        }
        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func followUser(sessionManagementToken: String, username: String, category: String? = nil) async throws -> Data {
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

        // A present-but-invalid category is rejected; nil uses the default (#392).
        if let category, FollowCategory(rawValue: category) == nil {
            throw APIError.serverError(statusCode: 400, serverMessage: "Invalid category")
        }

        if isUserFollowing(from: currentUser.id, to: userToFollow.id) {
            throw APIError.badServerResponse(statusCode: 400) // Already following
        }

        let followCategory = category ?? FollowCategory.following.rawValue
        userFollows.append(MockUserFollow(
            userFromId: currentUser.id, userToId: userToFollow.id, category: followCategory))

        struct Fields: Codable {
            let message: String
            let follow_category: String
        }
        return try createSerializedResponse(fields: Fields(message: "User followed", follow_category: followCategory))
    }

    func setFollowCategory(sessionManagementToken: String, username: String, category: String) async throws -> Data {
        await simulateNetwork()
        guard let currentUser = findUser(bySessionToken: sessionManagementToken) else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        guard let target = findUser(byUsername: username) else {
            throw APIError.badServerResponse(statusCode: 400)
        }
        if currentUser.id == target.id {
            throw APIError.serverError(statusCode: 400, serverMessage: "Cannot categorize self")
        }
        guard FollowCategory(rawValue: category) != nil else {
            throw APIError.serverError(statusCode: 400, serverMessage: "Invalid category")
        }
        guard let index = userFollows.firstIndex(where: {
            $0.userFromId == currentUser.id && $0.userToId == target.id
        }) else {
            throw APIError.serverError(statusCode: 400, serverMessage: "Not following user")
        }
        userFollows[index].category = category

        struct Fields: Codable {
            let message: String
            let follow_category: String
        }
        return try createSerializedResponse(fields: Fields(message: "Category updated", follow_category: category))
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
        
        // 4. Check if the requesting user is following the profile user, and
        //    with which relationship category (issue #392).
        let followEdge = userFollows.first(where: {
            $0.userFromId == requestingUser.id && $0.userToId == profileUser.id
        })
        let isFollowing = followEdge != nil
        let isBlocked = requestingUser.blocked.contains(profileUser.id)
        let isBlockedBy = requestingUser.blockedBy.contains(profileUser.id)

        // 5. Build the response data (matching the Swift struct). The owner-only
        // photo moderation fields (issue #7) are present only when viewing your
        // own profile; they're nil (and so read back as absent) otherwise,
        // mirroring the backend.
        let isOwnProfile = profileUser.id == requestingUser.id
        // Only an approved photo is exposed, and never to someone the target has
        // blocked (mirrors the website stub's liveAvatar).
        let liveAvatar: String? = (isBlockedBy || profileUser.profileImageStatus != "approved")
            ? nil : profileUser.profileImageUrl
        struct Fields: Codable {
            let username: String
            let post_count: Int
            let follower_count: Int
            let following_count: Int
            let is_following: Bool
            let follow_category: String?
            let is_blocked: Bool
            let identity_is_verified: Bool
            let is_adult: Bool
            let membership_number: Int?
            let profile_image_url: String?
            let profile_image_original_url: String?
            // Owner-only (issue #7).
            let profile_image_status: String?
            let profile_image_reason_code: String?
            let pending_profile_image_url: String?
            // Public bio (issue #380).
            let bio: String
        }

        if isBlockedBy {
             let fields = Fields(
                username: profileUser.username,
                post_count: 0,
                follower_count: 0,
                following_count: 0,
                is_following: false,
                follow_category: nil,
                is_blocked: isBlocked,
                identity_is_verified: false,
                is_adult: false,
                membership_number: profileUser.membershipNumber,
                profile_image_url: nil,
                profile_image_original_url: nil,
                profile_image_status: nil,
                profile_image_reason_code: nil,
                pending_profile_image_url: nil,
                // Redacted for a blocked requester, like the stats/avatar above.
                bio: ""
            )
            return try createSerializedResponse(fields: fields)
        }

        let fields = Fields(
            username: profileUser.username,
            post_count: postCount,
            follower_count: followerCount,
            following_count: followingCount,
            is_following: isFollowing,
            follow_category: followEdge?.category,
            is_blocked: isBlocked,
            identity_is_verified: profileUser.identityIsVerified,
            is_adult: profileUser.isAdult,
            membership_number: profileUser.membershipNumber,
            profile_image_url: liveAvatar,
            profile_image_original_url: liveAvatar,
            profile_image_status: isOwnProfile ? profileUser.profileImageStatus : nil,
            profile_image_reason_code: isOwnProfile ? profileUser.profileImageReasonCode : nil,
            pending_profile_image_url: isOwnProfile ? profileUser.pendingProfileImageUrl : nil,
            bio: profileUser.bio
        )

        // 6. Return the data using your existing helper
        return try createSerializedResponse(fields: fields)
    }

    // MARK: - Profile Photo (issue #7)

    func setProfilePhoto(sessionManagementToken: String, imageURL: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken),
              let userIndex = users.firstIndex(where: { $0.id == user.id })
        else { throw APIError.badServerResponse(statusCode: 400) }
        // The real backend stores the photo pending and classifies it off the
        // request path; the stub has no classifier, so — like the backend's
        // eager (no-Redis) mode — it approves immediately, while the response
        // still reports the initial "pending" state so clients exercise the
        // review-then-approve path.
        users[userIndex].profileImageUrl = imageURL
        users[userIndex].pendingProfileImageUrl = nil
        users[userIndex].profileImageStatus = "approved"
        users[userIndex].profileImageReasonCode = nil
        struct Fields: Codable { let profile_image_status: String; let message: String }
        return try createSerializedResponse(fields: Fields(
            profile_image_status: "pending",
            message: "Your photo is being reviewed and will be shown once it is approved."
        ))
    }

    func removeProfilePhoto(sessionManagementToken: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken),
              let userIndex = users.firstIndex(where: { $0.id == user.id })
        else { throw APIError.badServerResponse(statusCode: 400) }
        users[userIndex].profileImageUrl = nil
        users[userIndex].pendingProfileImageUrl = nil
        users[userIndex].profileImageStatus = "none"
        users[userIndex].profileImageReasonCode = nil
        struct Fields: Codable { let profile_image_status: String; let message: String }
        return try createSerializedResponse(fields: Fields(
            profile_image_status: "none",
            message: "Your profile photo has been removed."
        ))
    }

    // MARK: - Bio (issue #380)

    func setBio(sessionManagementToken: String, bio: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken),
              let userIndex = users.firstIndex(where: { $0.id == user.id })
        else { throw APIError.badServerResponse(statusCode: 401) }
        struct Fields: Codable { let bio: String; let message: String }
        // A blank bio just clears it — nothing to moderate.
        if bio.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            users[userIndex].bio = ""
            return try createSerializedResponse(fields: Fields(bio: "", message: "Your bio has been cleared."))
        }
        // Rejections throw serverError with the backend's message (not
        // badServerResponse), mirroring how RealAPI surfaces a 4xx that carries a
        // JSON {"error": ...} body — which every set_bio rejection does — so the
        // view model's actionable-message path is exercised as in production.
        //
        // Count Unicode code points (like the backend's Python len() and the
        // CharacterCounter helper), not grapheme clusters, so emoji/combined-
        // character bios are judged the same way here as in production.
        if bio.unicodeScalars.count > GVOAppConstants.maxBioLength {
            throw APIError.serverError(statusCode: 400, serverMessage: "Bio exceeds maximum length of \(GVOAppConstants.maxBioLength) characters")
        }
        // The backend disallows the semicolon in user text; mirror that here.
        if bio.contains(";") {
            throw APIError.serverError(statusCode: 400, serverMessage: "Your bio cannot contain a semicolon (;).")
        }
        // The stub has no classifier; like the backend's TESTING text classifier
        // it rejects anything containing "negative" and accepts the rest, so
        // tests can drive the reject path. A rejected bio is never stored.
        if bio.lowercased().contains("negative") {
            throw APIError.serverError(statusCode: 400, serverMessage: "Text is not positive because your bio did not meet our guidelines.")
        }
        users[userIndex].bio = bio
        return try createSerializedResponse(fields: Fields(bio: bio, message: "Your bio has been updated."))
    }

    // MARK: - Positive interest tags (issues #446/#35)

    /// Mirrors the backend apply_user_interests: full-replace of a user's
    /// interest state. Known preset slugs are kept; each freeform term is
    /// positivity-checked (reject anything containing "negative", like the
    /// backend TESTING classifier) and mapped to buckets; the weighting set is
    /// the union of picks and mapped buckets. Returns the applied result.
    private func applyInterests(atIndex index: Int, categories: [String], freeform: [String]) -> SetInterestsResponse {
        // Normalize before matching, mirroring the backend's strip().lower().
        var picked: [String] = []
        for raw in categories {
            let slug = raw.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            if InterestVocabulary.slugs.contains(slug) && !picked.contains(slug) {
                picked.append(slug)
            }
        }

        var accepted: [String] = []
        var rejected: [RejectedInterest] = []
        var union = Set(picked)
        var seen = Set<String>()

        for raw in freeform {
            let term = raw.trimmingCharacters(in: .whitespacesAndNewlines)
            if term.isEmpty { continue }
            // Dedupe before deciding the term's fate and bound the rejected
            // list, mirroring the backend's _normalize_freeform_terms: deduping
            // only accepted terms let a repeated bad term be reported once per
            // occurrence, and an unbounded list diverges from the real API
            // (duplicate ForEach ids, inflated responses).
            let key = term.lowercased()
            if seen.contains(key) { continue }
            seen.insert(key)
            if term.unicodeScalars.count > GVOAppConstants.maxFreeformInterestLength {
                if rejected.count < GVOAppConstants.maxFreeformInterests {
                    // Echo bounded like the backend bounds it, so a huge term
                    // can't produce a huge response.
                    let echo = term.unicodeScalars.count > GVOAppConstants.rejectedTextEchoLimit
                        ? String(term.prefix(GVOAppConstants.rejectedTextEchoLimit)) + "…"
                        : term
                    rejected.append(RejectedInterest(text: echo, reasonCode: "too_long",
                        reason: "is longer than \(GVOAppConstants.maxFreeformInterestLength) characters"))
                }
                continue
            }
            if key.contains("negative") {
                if rejected.count < GVOAppConstants.maxFreeformInterests {
                    rejected.append(RejectedInterest(text: key, reasonCode: "guidelines",
                        reason: "did not meet our positivity guidelines"))
                }
                continue
            }
            accepted.append(key)
            for slug in InterestVocabulary.matchSlugs(key) { union.insert(slug) }
            if accepted.count >= GVOAppConstants.maxFreeformInterests { break }
        }

        users[index].freeformInterests = accepted
        users[index].interestCategories = union.sorted()
        return SetInterestsResponse(
            categories: union.sorted(),
            freeform: InterestFreeformResult(accepted: accepted, rejected: rejected),
            message: "Your interests have been updated.")
    }

    func getInterestOptions() async throws -> Data {
        await simulateNetwork()
        struct Fields: Codable { let options: [InterestOption] }
        return try createSerializedResponse(fields: Fields(options: InterestVocabulary.options))
    }

    func getInterests(sessionManagementToken: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else {
            throw APIError.badServerResponse(statusCode: 401)
        }
        struct Fields: Codable { let categories: [String]; let freeform: [String] }
        return try createSerializedResponse(fields: Fields(
            categories: user.interestCategories, freeform: user.freeformInterests))
    }

    func setInterests(sessionManagementToken: String, categories: [String], freeform: [String]) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken),
              let index = users.firstIndex(where: { $0.id == user.id })
        else { throw APIError.badServerResponse(statusCode: 401) }
        let result = applyInterests(atIndex: index, categories: categories, freeform: freeform)
        struct RejectedFields: Codable { let text: String; let reason_code: String?; let reason: String? }
        struct FreeformFields: Codable { let accepted: [String]; let rejected: [RejectedFields] }
        struct Fields: Codable { let categories: [String]; let freeform: FreeformFields; let message: String? }
        return try createSerializedResponse(fields: Fields(
            categories: result.categories,
            freeform: FreeformFields(
                accepted: result.freeform.accepted,
                rejected: result.freeform.rejected.map {
                    RejectedFields(text: $0.text, reason_code: $0.reasonCode, reason: $0.reason)
                }),
            message: result.message))
    }

    // MARK: - Push notifications (issue #342/#343)

    func registerDevice(sessionManagementToken: String, platform: String, token: String) async throws -> Data {
        await simulateNetwork()
        // The stub keeps no device table; registration just "succeeds" for a
        // valid session so the push bootstrap can be exercised in UI mode.
        guard findUser(bySessionToken: sessionManagementToken) != nil else {
            throw APIError.badServerResponse(statusCode: 401)
        }
        struct Fields: Codable { let message: String }
        return try createSerializedResponse(fields: Fields(message: "Device registered."))
    }

    // Per-type push preferences, mirroring the backend's PUSH_TYPE_CHOICES.
    // Defaults to enabled; toggling stores an override in this map.
    private var notificationOverrides: [String: Bool] = [:]

    func getNotificationPreferences(sessionManagementToken: String) async throws -> Data {
        await simulateNetwork()
        guard findUser(bySessionToken: sessionManagementToken) != nil else {
            throw APIError.badServerResponse(statusCode: 401)
        }
        let prefs = [NotificationPreference(
            type: "post_rejected", label: "Post moderation",
            enabled: notificationOverrides["post_rejected"] ?? true)]
        return try createSerializedResponse(fields: NotificationPreferencesResponse(preferences: prefs))
    }

    func setNotificationPreference(sessionManagementToken: String, notificationType: String, enabled: Bool) async throws -> Data {
        await simulateNetwork()
        guard findUser(bySessionToken: sessionManagementToken) != nil else {
            throw APIError.badServerResponse(statusCode: 401)
        }
        notificationOverrides[notificationType] = enabled
        struct Fields: Codable { let type: String; let enabled: Bool }
        return try createSerializedResponse(fields: Fields(type: notificationType, enabled: enabled))
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
            let caption_font: String
            let background_color: String
            let hidden_reason: String
            let has_appeal: Bool
        }
        guard startIndex < hidden.count else { return try createSerializedListResponse(fieldsList: [Fields]()) }
        let endIndex = min(startIndex + pageSize, hidden.count)

        let fields = hidden[startIndex..<endIndex].map {
            Fields(post_identifier: $0.postIdentifier, image_url: $0.imageURL, caption: $0.caption,
                   caption_font: $0.captionFont, background_color: $0.backgroundColor,
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
            let body_formatting: [CommentFormatSpan]?
            let hidden_reason: String
            let has_appeal: Bool
        }
        guard startIndex < hidden.count else { return try createSerializedListResponse(fieldsList: [Fields]()) }
        let endIndex = min(startIndex + pageSize, hidden.count)

        let fields = hidden[startIndex..<endIndex].map {
            Fields(comment_identifier: $0.commentIdentifier, body: $0.body,
                   body_formatting: $0.bodyFormatting,
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

