import Foundation

// MARK: - In-Memory Data Models
// These structs simulate the Django database models.

fileprivate struct MockUser {
    let id = UUID()
    var username: String
    var email: String
    var passwordHash: String // Storing plain text for mock purposes.
    var resetId: Int = -1
    var identityIsVerified: Bool = false
}

fileprivate struct MockSession {
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
    var imageURL: String
    var caption: String
    var likes: [String] = [] // Usernames of likers
    var reports: [(username: String, reason: String)] = []
    var commentThreads: [MockCommentThread] = []
    var isHidden: Bool = false
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
    let createdDate = Date()
    var updatedDate = Date()
}

fileprivate struct DjangoSerializedObject<F: Codable>: Codable {
    var model: String = "app.response"
    var pk: String? = nil
    let fields: F
}

// MARK: - Stateful API Implementation
final class StatefulStubbedAPI: APIProtocol {

    // MARK: - In-Memory "Database"
    private var users: [MockUser] = []
    private var sessions: [MockSession] = []
    private var loginCookies: [MockLoginCookie] = []
    private var posts: [MockPost] = []
    private var commentThreads: [MockCommentThread] = []
    private var comments: [MockComment] = []

    // MARK: - Configuration
    public var simulatedLatency: TimeInterval = 0.1
    private let maxReportsBeforeHiding = 5

    // MARK: - Private Finders
    private func findUser(byUsernameOrEmail id: String) -> MockUser? { users.first { $0.username == id || $0.email == id } }
    private func findUser(byUsername name: String) -> MockUser? { users.first { $0.username == name } }
    private func findUser(byEmail email: String) -> MockUser? { users.first { $0.email == email } }
    private func findUser(byUsername name: String, andEmail email: String) -> MockUser? { users.first { $0.username == name && $0.email == email } }
    private func findSession(byToken token: String) -> MockSession? { sessions.first { $0.managementToken == token } }
    private func findUser(bySessionToken token: String) -> MockUser? {
        guard let session = findSession(byToken: token) else { return nil }
        return users.first { $0.id == session.userId }
    }
    private func findPost(byIdentifier id: String) -> MockPost? { posts.first { $0.postIdentifier == id } }
    private func findCommentThread(byIdentifier id: String) -> MockCommentThread? { commentThreads.first { $0.commentThreadIdentifier == id } }
    private func findComment(byIdentifier id: String) -> MockComment? { comments.first { $0.commentIdentifier == id } }

    // MARK: - Private Helpers
    private func createSerializedResponse<T: Codable>(fields: T) throws -> Data {
        let serializedObject = DjangoSerializedObject(fields: fields)
        let serializedListData = try JSONEncoder().encode([serializedObject])
        let listString = String(data: serializedListData, encoding: .utf8)!
        return try JSONEncoder().encode(["response_list": listString])
    }
    
    private func createSerializedListResponse<T: Codable>(fieldsList: [T]) throws -> Data {
        let serializedObjects = fieldsList.map { DjangoSerializedObject(fields: $0) }
        let serializedListData = try JSONEncoder().encode(serializedObjects)
        let listString = String(data: serializedListData, encoding: .utf8)!
        return try JSONEncoder().encode(["response_list": listString])
    }

    private func createEmptySuccessResponse() throws -> Data {
        struct EmptyFields: Codable {}
        return try createSerializedResponse(fields: EmptyFields())
    }
    private func simulateNetwork() async { try? await Task.sleep(for: .seconds(simulatedLatency)) }
    private func generateToken() -> String { UUID().uuidString.replacingOccurrences(of: "-", with: "") }

    // MARK: - Implementations
    
    func register(username: String, email: String, password: String, rememberMe: String, ip: String) async throws -> Data {
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
            struct Fields: Codable { let series_identifier, login_cookie_token, session_management_token: String }
            return try createSerializedResponse(fields: Fields(series_identifier: cookie.seriesIdentifier, login_cookie_token: cookie.token, session_management_token: newSession.managementToken))
        } else {
            struct Fields: Codable { let session_management_token: String }
            return try createSerializedResponse(fields: Fields(session_management_token: newSession.managementToken))
        }
    }

    func loginUser(usernameOrEmail: String, password: String, rememberMe: String, ip: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(byUsernameOrEmail: usernameOrEmail) else { throw APIError.badServerResponse(statusCode: 400) }
        if user.passwordHash != password { throw APIError.badServerResponse(statusCode: 400) }
        
        sessions.removeAll { $0.userId == user.id }
        let newSession = MockSession(managementToken: generateToken(), userId: user.id, ip: ip)
        sessions.append(newSession)
        
        let wantsRememberMe = Bool(rememberMe.lowercased()) ?? false
        if wantsRememberMe {
            let cookie = MockLoginCookie(seriesIdentifier: UUID().uuidString, token: generateToken(), userId: user.id)
            loginCookies.append(cookie)
            struct Fields: Codable { let series_identifier, login_cookie_token, session_management_token: String }
            return try createSerializedResponse(fields: Fields(series_identifier: cookie.seriesIdentifier, login_cookie_token: cookie.token, session_management_token: newSession.managementToken))
        } else {
            struct Fields: Codable { let session_management_token: String }
            return try createSerializedResponse(fields: Fields(session_management_token: newSession.managementToken))
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
        
        // --- SIMULATED LOGIC ---
        // On success, issue a new cookie token AND a new session token.
        // NOTE: This assumes the backend's intent is to grant a full session.
        
        // 1. Update the login cookie with a new token
        let newCookieToken = generateToken()
        loginCookies[cookieIndex].token = newCookieToken
        
        // 2. Create a new session for the user
        let newSession = MockSession(managementToken: generateToken(), userId: user.id, ip: ip)
        sessions.append(newSession)

        // 3. Return both the new cookie and the new session token
        struct Fields: Codable {
            let login_cookie_token: String
            let session_management_token: String
        }
        let fields = Fields(login_cookie_token: newCookieToken, session_management_token: newSession.managementToken)
        return try createSerializedResponse(fields: fields)
    }


    func requestPasswordReset(usernameOrEmail: String) async throws -> Data {
        await simulateNetwork()
        guard let userIndex = users.firstIndex(where: { $0.username == usernameOrEmail || $0.email == usernameOrEmail }) else { throw APIError.badServerResponse(statusCode: 400) }
        let resetId = Int.random(in: 100000...999999)
        users[userIndex].resetId = resetId
        print("Password reset ID for \(users[userIndex].username) is: \(resetId)") // Simulate sending email
        return try createEmptySuccessResponse()
    }

    func verifyPasswordReset(usernameOrEmail: String, resetID: Int) async throws -> Data {
        await simulateNetwork()
        guard let userIndex = users.firstIndex(where: { $0.username == usernameOrEmail || $0.email == usernameOrEmail }) else { throw APIError.badServerResponse(statusCode: 400) }
        if users[userIndex].resetId == resetID && users[userIndex].resetId != -1 {
            users[userIndex].resetId = -1
            return try createEmptySuccessResponse()
        }
        throw APIError.badServerResponse(statusCode: 400)
    }

    func resetPassword(username: String, email: String, newPassword: String) async throws -> Data {
        await simulateNetwork()
        guard let userIndex = users.firstIndex(where: { $0.username == username && $0.email == email }) else { throw APIError.badServerResponse(statusCode: 400) }
        users[userIndex].passwordHash = newPassword
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

    func makePost(sessionManagementToken: String, imageURL: String, caption: String) async throws -> Data {
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        let newPost = MockPost(authorId: user.id, imageURL: imageURL, caption: caption)
        posts.append(newPost)
        struct Fields: Codable { let post_identifier: String }
        return try createSerializedResponse(fields: Fields(post_identifier: newPost.postIdentifier))
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
        if posts[postIndex].reports.count > maxReportsBeforeHiding { posts[postIndex].isHidden = true }
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
        await simulateNetwork()
        guard let user = findUser(bySessionToken: sessionManagementToken) else { throw APIError.badServerResponse(statusCode: 400) }
        let relevantPosts = posts.filter { $0.authorId != user.id && !$0.isHidden }.sorted { $0.createdDate > $1.createdDate }
        if relevantPosts.isEmpty { throw APIError.badServerResponse(statusCode: 400) }

        struct Fields: Codable { let post_identifier: String; let image_url: String }
        let fieldObjects = relevantPosts.map { Fields(post_identifier: $0.postIdentifier, image_url: $0.imageURL) }
        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func getPostsForUser(sessionManagementToken: String, username: String, batch: Int) async throws -> Data {
        await simulateNetwork()
        guard findUser(bySessionToken: sessionManagementToken) != nil else { throw APIError.badServerResponse(statusCode: 400) }
        guard let targetUser = findUser(byUsername: username) else { throw APIError.badServerResponse(statusCode: 400) }
        let relevantPosts = posts.filter { $0.authorId == targetUser.id && !$0.isHidden }
        if relevantPosts.isEmpty { throw APIError.badServerResponse(statusCode: 400) }
        
        struct Fields: Codable { let post_identifier: String; let image_url: String }
        let fieldObjects = relevantPosts.map { Fields(post_identifier: $0.postIdentifier, image_url: $0.imageURL) }
        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func getPostDetails(postIdentifier: String) async throws -> Data {
        await simulateNetwork()
        guard let post = findPost(byIdentifier: postIdentifier) else { throw APIError.badServerResponse(statusCode: 400) }
        struct Fields: Codable { let post_identifier, image_url, caption: String; let post_likes: Int }
        let fields = Fields(post_identifier: post.postIdentifier, image_url: post.imageURL, caption: post.caption, post_likes: post.likes.count)
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
        if comments[commentIndex].reports.count > maxReportsBeforeHiding { comments[commentIndex].isHidden = true }
        return try createEmptySuccessResponse()
    }

    func getCommentsForPost(postIdentifier: String, batch: Int) async throws -> Data {
        await simulateNetwork()
        let relevantThreads = commentThreads.filter { $0.postId == postIdentifier }
        if relevantThreads.isEmpty { throw APIError.badServerResponse(statusCode: 400) }

        struct Fields: Codable { let comment_thread_identifier: String }
        let fieldObjects = relevantThreads.map { Fields(comment_thread_identifier: $0.commentThreadIdentifier) }
        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func getCommentsForThread(commentThreadIdentifier: String, batch: Int) async throws -> Data {
        await simulateNetwork()
        let relevantComments = comments.filter { $0.threadId == commentThreadIdentifier && !$0.isHidden }.sorted { $0.createdDate < $1.createdDate }
        if relevantComments.isEmpty { throw APIError.badServerResponse(statusCode: 400) }

        struct Fields: Codable {
            let comment_identifier, body, author_username: String
            let comment_creation_time, comment_updated_time: String
            let comment_likes: Int
        }
        
        let dateFormatter = ISO8601DateFormatter()
        let fieldObjects = relevantComments.map { comment in
            Fields(comment_identifier: comment.commentIdentifier, body: comment.body, author_username: comment.authorUsername,
                   comment_creation_time: dateFormatter.string(from: comment.createdDate),
                   comment_updated_time: dateFormatter.string(from: comment.updatedDate),
                   comment_likes: comment.likes.count)
        }
        return try createSerializedListResponse(fieldsList: fieldObjects)
    }

    func getUsersMatchingFragment(sessionManagementToken: String, usernameFragment: String) async throws -> Data {
        await simulateNetwork()
        guard findUser(bySessionToken: sessionManagementToken) != nil else { throw APIError.badServerResponse(statusCode: 400) }
        let matchingUsers = users.filter { $0.username.lowercased().starts(with: usernameFragment.lowercased()) }
        
        struct Fields: Codable { let username: String; let identity_is_verified: Bool }
        let fieldObjects = matchingUsers.map { Fields(username: $0.username, identity_is_verified: $0.identityIsVerified) }
        return try createSerializedListResponse(fieldsList: fieldObjects)
    }
}

