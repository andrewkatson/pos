//
//  RealAPI.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/5/25.
//

import Foundation

// MARK: - API Error Definition
/// Defines specific errors that can occur during an API call.
///
enum APIError: Error, LocalizedError {
    case invalidURL
    case badServerResponse(statusCode: Int)
    case serverError(statusCode: Int, serverMessage: String)
    case requestFailed(Error)
    case decodingError(Error)
    case encodingError(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "The URL provided was invalid."
        case .badServerResponse(let statusCode):
            return "The server returned an unsuccessful status code: \(statusCode)."
        case .serverError(_, let message):
            return message
        case .requestFailed(let error):
            return "The network request failed: \(error.localizedDescription)."
        case .decodingError(let error):
            return "Failed to decode the server response: \(error.localizedDescription)."
        case .encodingError(let error):
            return "Failed to encode the request body: \(error.localizedDescription)."
        }
    }
}

// MARK: - Real API Implementation
/// A concrete class that implements the APIProtocol to make live network requests.
final class RealAPI: Networking {
    
    /// The base URL for all API endpoints. Remember to replace this with your actual server address.
    private let baseURL = "https://api.smiling.social/user_index/"
    
    /// Defines the HTTP methods used by the API.
    private enum HTTPMethod: String {
        case get = "GET"
        case post = "POST"
    }
    
    // MARK: - Request Body Structs
    // Defines all Encodable structs used for JSON request bodies.
    
    private struct RegisterBody: Encodable {
        let username: String
        let email: String
        let password: String
        let remember_me: String
        let ip: String
        let date_of_birth: String
    }

    private struct VerifyIdentityBody: Encodable {
        let date_of_birth: String
    }
    
    private struct LoginBody: Encodable {
        let username_or_email: String
        let password: String
        let remember_me: String
        let ip: String
    }
    
    private struct RememberMeBody: Encodable {
        let session_management_token: String
        let series_identifier: String
        let login_cookie_token: String
        let ip: String
    }
    
    private struct ResetPasswordBody: Encodable {
        let username: String
        let email: String
        let password: String
        let reset_token: String
    }

    private struct RequestResetBody: Encodable {
        let username_or_email: String
    }

    private struct VerifyResetBody: Encodable {
        let username_or_email: String
        let verification_token: String
    }

    private struct VerifyEmailBody: Encodable {
        let verification_token: String
    }

    private struct ResendVerificationEmailBody: Encodable {
        let username_or_email: String
    }
    
    private struct MakePostBody: Encodable {
        let image_url: String
        let caption: String
    }
    
    private struct ReportBody: Encodable { // Re-used for posts and comments
        let reason: String
    }
    
    private struct CommentBody: Encodable {
        let comment_text: String
    }

    private struct SubmitAppealBody: Codable {
        let target_type: String
        let target_identifier: String
        let reason: String
    }

    // MARK: - Private Helpers
    
    /// Encodes an `Encodable` value into `Data`.
    /// - Throws: `APIError.encodingError` if serialization fails.
    private func encode<T: Encodable>(_ body: T) throws -> Data {
        do {
            let encoder = JSONEncoder()
            // Can configure encoder here if needed (e.g., date strategies)
            return try encoder.encode(body)
        } catch {
            throw APIError.encodingError(error)
        }
    }
    
    /// A generic helper function to perform a network request.
    /// - Parameter pathSegments: The components of the URL path that will be joined by `/`.
    /// - Parameter method: The HTTP method to use (e.g., .get, .post).
    /// - Parameter body: Optional `Data` to be sent as the request body (for POST).
    /// - Parameter authToken: Optional token for the `Authorization: Bearer` header.
    /// - Returns: The raw `Data` from the server response.
    /// - Throws: An `APIError` if the request fails at any stage.
    private func performRequest(
        pathSegments: [String],
        method: HTTPMethod,
        body: Data? = nil,
        authToken: String? = nil
    ) async throws -> Data {
        
        // 1. Construct a safe URL from the path segments
        var urlComponents = URLComponents(string: baseURL)
        let basePath = urlComponents?.path ?? ""
        let path = pathSegments.map {
            // Ensure each path component is properly encoded
            $0.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? ""
        }.joined(separator: "/")
        
        let fullPath = basePath + path + "/"
        urlComponents?.path = fullPath.replacingOccurrences(of: "//", with: "/")
        
        guard let url = urlComponents?.url else {
            throw APIError.invalidURL
        }
        
        // 2. Create the request and set the method
        var request = URLRequest(url: url)
        request.httpMethod = method.rawValue
        
        // 3. Add Headers
        if let authToken = authToken {
            request.setValue("\(GVOAppConstants.bearer) \(authToken)", forHTTPHeaderField: GVOAppConstants.authHeaderField)
        }
        
        // 4. Add Body
        if let body = body {
            request.httpBody = body
            request.setValue(GVOAppConstants.requestType, forHTTPHeaderField: GVOAppConstants.httpHeaderField)
        }
        
        // 5. Perform the network call
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            // 6. Validate the HTTP response
            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.badServerResponse(statusCode: -1) // Should not happen with HTTP/S
            }
            
            guard (200...299).contains(httpResponse.statusCode) else {
                // Try to extract the server's error message from the response body
                struct ServerErrorBody: Decodable { let error: String? }
                if let body = try? JSONDecoder().decode(ServerErrorBody.self, from: data),
                   let message = body.error {
                    // Only authenticated requests signal a forced logout: a
                    // banned login attempt is handled by the login screen.
                    // TODO: NotificationCenter here is a UIKit-era pattern.
                    // Replace with a more SwiftUI-native signal (e.g. an async
                    // stream or an injected observable the API holds) so the
                    // forced-logout path doesn't lean on global broadcast.
                    if authToken != nil && message == GVOAppConstants.accountBannedError {
                        NotificationCenter.default.post(name: .accountBanned, object: nil)
                    }
                    // An unverified email blocks every authenticated endpoint,
                    // so the local session is useless — drop it like a ban.
                    if authToken != nil && message == GVOAppConstants.emailNotVerifiedError {
                        NotificationCenter.default.post(name: .emailNotVerified, object: nil)
                    }
                    throw APIError.serverError(statusCode: httpResponse.statusCode, serverMessage: sanitizeErrorMessage(message))
                }
                throw APIError.badServerResponse(statusCode: httpResponse.statusCode)
            }
            
            // 7. Return the response data
            return data
        } catch let error as APIError {
            throw error // Re-throw our specific API errors
        } catch {
            throw APIError.requestFailed(error) // Wrap other errors
        }
    }
    
    // MARK: - User & Session Management
    
    /// Creates a user if they do not exist.
    func register(username: String, email: String, password: String, rememberMe: String, ip: String, dateOfBirth: String) async throws -> Data {
        let body = RegisterBody(username: username, email: email, password: password, remember_me: rememberMe, ip: ip, date_of_birth: dateOfBirth)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentRegister],
            method: .post,
            body: requestBody
        )
    }
    
    /// Logs the user in if they exist.
    func loginUser(usernameOrEmail: String, password: String, rememberMe: String, ip: String) async throws -> Data {
        let body = LoginBody(username_or_email: usernameOrEmail, password: password, remember_me: rememberMe, ip: ip)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentLogin],
            method: .post,
            body: requestBody
        )
    }
    
    /// Logs the user in using a "remember me" token.
    func loginUserWithRememberMe(sessionManagementToken: String, seriesIdentifier: String, loginCookieToken: String, ip: String) async throws -> Data {
        let body = RememberMeBody(
            session_management_token: sessionManagementToken,
            series_identifier: seriesIdentifier,
            login_cookie_token: loginCookieToken,
            ip: ip
        )
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentLogin, GVOAppConstants.pathSegmentRemember],
            method: .post,
            body: requestBody
        )
    }
    
    /// Resets the user's password.
    func resetPassword(username: String, email: String, newPassword: String, resetToken: String) async throws -> Data {
        let body = ResetPasswordBody(username: username, email: email, password: newPassword, reset_token: resetToken)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPassword, GVOAppConstants.pathSegmentReset],
            method: .post,
            body: requestBody
        )
    }
    
    /// Requests a password reset and sends the user an email.
    func requestPasswordReset(usernameOrEmail: String) async throws -> Data {
        let body = RequestResetBody(username_or_email: usernameOrEmail)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPassword, GVOAppConstants.pathSegmentRequestReset],
            method: .post,
            body: requestBody
        )
    }
    
    /// Verifies the password reset token received via email.
    func verifyPasswordReset(usernameOrEmail: String, verificationToken: String) async throws -> Data {
        let body = VerifyResetBody(username_or_email: usernameOrEmail, verification_token: verificationToken)
        let requestBody = try encode(body)
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPassword, GVOAppConstants.pathSegmentVerifyReset],
            method: .post,
            body: requestBody
        )
    }

    /// Verifies the account's email address with the token from the welcome email.
    func verifyEmail(verificationToken: String) async throws -> Data {
        let body = VerifyEmailBody(verification_token: verificationToken)
        let requestBody = try encode(body)
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentVerifyEmail],
            method: .post,
            body: requestBody
        )
    }

    /// Sends a fresh email-verification link, invalidating the previous one.
    func resendVerificationEmail(usernameOrEmail: String) async throws -> Data {
        let body = ResendVerificationEmailBody(username_or_email: usernameOrEmail)
        let requestBody = try encode(body)
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentResendVerificationEmail],
            method: .post,
            body: requestBody
        )
    }
    
    /// Logs the user out.
    func logoutUser(sessionManagementToken: String) async throws -> Data {
        // This is a POST request, no body, with auth.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentLogout],
            method: .post,
            authToken: sessionManagementToken
        )
    }
    
    /// Deletes the user account.
    func deleteUser(sessionManagementToken: String) async throws -> Data {
        // This is a POST request, no body, with auth.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentUser, GVOAppConstants.pathSegmentDelete],
            method: .post,
            authToken: sessionManagementToken
        )
    }
        
        
    /// Verifies the identity of the user
    func verifyIdentity(sessionManagementToken: String, dateOfBirth: String) async throws -> Data {
        let body = VerifyIdentityBody(date_of_birth: dateOfBirth)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentVerifyIdentity],
            method: .post,
            body: requestBody,
            authToken: sessionManagementToken
        )
    }
    
    /// Follow a user
    func followUser(sessionManagementToken: String, username: String) async throws -> Data {
        // This is a POST request, no body, with auth. Username is in path.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentUsers, username, GVOAppConstants.pathSegmentFollow],
            method: .post,
            authToken: sessionManagementToken
        )
    }
    
    /// Unfollow a user
    func unfollowUser(sessionManagementToken: String, username: String) async throws -> Data {
        // This is a POST request, no body, with auth. Username is in path.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentUsers, username, GVOAppConstants.pathSegmentUnfollow],
            method: .post,
            authToken: sessionManagementToken
        )
    }
    
    /// Block or unblock a user
    func toggleBlock(sessionManagementToken: String, username: String) async throws -> Data {
        // This is a POST request, no body, with auth. Username is in path.
        // URL pattern: users/<str:username_to_toggle_block>/block/
        // Wait, backend URL is `users/<username>/block/`.
        // My RealAPI seems to use older patterns like `unfollow_user`.
        // But `toggle_block` view URL was added as: `path('users/<str:username_to_toggle_block>/block/', views.toggle_block, name='toggle_block')`
        // So the path segments should be ["users", username, "block"]
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentUsers, username, GVOAppConstants.pathSegmentBlock],
            method: .post,
            authToken: sessionManagementToken
        )
    }
    
    // MARK: - Post Management

    /// Requests a backend-issued presigned S3 PUT URL for a new post image.
    func createUploadUrl(sessionManagementToken: String) async throws -> Data {
        // This is a POST request, no body, with auth.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPosts, GVOAppConstants.pathSegmentUploadUrl],
            method: .post,
            authToken: sessionManagementToken
        )
    }

    /// Creates and stores a new post.
    func makePost(sessionManagementToken: String, imageURL: String, caption: String) async throws -> Data {
        let body = MakePostBody(image_url: imageURL, caption: caption)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPosts, GVOAppConstants.pathSegmentCreate],
            method: .post,
            body: requestBody,
            authToken: sessionManagementToken
        )
    }
    
    /// Deletes a post.
    func deletePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        // This is a POST request, no body, with auth. ID is in path.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPosts, postIdentifier, GVOAppConstants.pathSegmentDelete],
            method: .post,
            authToken: sessionManagementToken
        )
    }
    
    /// Reports a post for a specific reason.
    func reportPost(sessionManagementToken: String, postIdentifier: String, reason: String) async throws -> Data {
        let body = ReportBody(reason: reason)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPosts, postIdentifier, GVOAppConstants.pathSegmentReport],
            method: .post,
            body: requestBody,
            authToken: sessionManagementToken
        )
    }
    
    /// Likes a post.
    func likePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        // This is a POST request, no body, with auth. ID is in path.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPosts, postIdentifier, GVOAppConstants.pathSegmentLike],
            method: .post,
            authToken: sessionManagementToken
        )
    }
    
    /// Unlikes a post.
    func unlikePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        // This is a POST request, no body, with auth. ID is in path.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPosts, postIdentifier,  GVOAppConstants.pathSegmentUnlike],
            method: .post,
            authToken: sessionManagementToken
        )
    }
    
    /// Gets all posts for the user's feed in batches.
    func getPostsInFeed(sessionManagementToken: String, batch: Int) async throws -> Data {
        // This is a GET request, no body, with auth. Batch is in path.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSregmenFeed, String(batch)],
            method: .get,
            authToken: sessionManagementToken
        )
    }
    
    /// Get all posts for a user's feed in batches for anyone they follow.
    func getPostsForFollowedUsers(sessionManagementToken: String, batch: Int) async throws -> Data {
        // This is a GET request, no body, with auth. Batch is in path.
        return try await performRequest(
            pathSegments: [ GVOAppConstants.pathSregmenFeed, GVOAppConstants.pathSegmentFollowed, String(batch)],
            method: .get,
            authToken: sessionManagementToken
        )
    }
    
    
    /// Gets a batch of posts for another user.
    func getPostsForUser(sessionManagementToken: String, username: String, batch: Int) async throws -> Data {
        // This is a GET request, no body, with auth. Username/Batch are in path.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentUsers, username, GVOAppConstants.pathSegmentPosts, String(batch)],
            method: .get,
            authToken: sessionManagementToken
        )
    }
    
    /// Gets the details for a single post.
    func getPostDetails(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        // Authenticated GET so the response can include the current user's like state. ID is in path.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPosts, postIdentifier, GVOAppConstants.pathSegmentDetails],
            method: .get,
            authToken: sessionManagementToken
        )
    }
    
    // MARK: - Comment Management
    
    /// Adds a direct comment to a post.
    func commentOnPost(sessionManagementToken: String, postIdentifier: String, commentText: String) async throws -> Data {
        let body = CommentBody(comment_text: commentText)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPosts, postIdentifier, GVOAppConstants.pathSegmentComment],
            method: .post,
            body: requestBody,
            authToken: sessionManagementToken
        )
    }

    /// Likes a specific comment within a post.
    func likeComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        // This is a POST request, no body, with auth. IDs are in path.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPosts, postIdentifier, GVOAppConstants.pathSegmentThreads, commentThreadIdentifier, GVOAppConstants.pathSegmentComments, commentIdentifier, GVOAppConstants.pathSegmentLike],
            method: .post,
            authToken: sessionManagementToken
        )
    }
    
    /// Unlikes a specific comment.
    func unlikeComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        // This is a POST request, no body, with auth. IDs are in path.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPosts, postIdentifier, GVOAppConstants.pathSegmentThreads, commentThreadIdentifier, GVOAppConstants.pathSegmentComments, commentIdentifier, GVOAppConstants.pathSegmentUnlike],
            method: .post,
            authToken: sessionManagementToken
        )
    }
    
    /// Deletes a comment.
    func deleteComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        // This is a POST request, no body, with auth. IDs are in path.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPosts, postIdentifier, GVOAppConstants.pathSegmentThreads, commentThreadIdentifier, GVOAppConstants.pathSegmentComments, commentIdentifier, GVOAppConstants.pathSegmentDelete],
            method: .post,
            authToken: sessionManagementToken
        )
    }
    
    /// Reports a comment for a specific reason.
    func reportComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String, reason: String) async throws -> Data {
        let body = ReportBody(reason: reason)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPosts, postIdentifier, GVOAppConstants.pathSegmentThreads, commentThreadIdentifier, GVOAppConstants.pathSegmentComments, commentIdentifier, GVOAppConstants.pathSegmentReport],
            method: .post,
            body: requestBody,
            authToken: sessionManagementToken
        )
    }
    
    /// Gets a batch of comment threads for a post.
    func getCommentsForPost(sessionManagementToken: String, postIdentifier: String, batch: Int) async throws -> Data {
        // Authenticated GET. ID/Batch are in path.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPosts, postIdentifier, GVOAppConstants.pathSegmentComments, String(batch)],
            method: .get,
            authToken: sessionManagementToken
        )
    }

    /// Gets a batch of comments for a specific comment thread.
    func getCommentsForThread(sessionManagementToken: String, commentThreadIdentifier: String, batch: Int) async throws -> Data {
        // Authenticated GET so each comment can include the current user's like state. ID/Batch are in path.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentThreads, commentThreadIdentifier, GVOAppConstants.pathSegmentComments, String(batch)],
            method: .get,
            authToken: sessionManagementToken
        )
    }
    
    /// Replies to a comment thread.
    func replyToCommentThread(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentText: String) async throws -> Data {
        let body = CommentBody(comment_text: commentText)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentPosts, postIdentifier, GVOAppConstants.pathSegmentThreads, commentThreadIdentifier, GVOAppConstants.pathSegmentReply],
            method: .post,
            body: requestBody,
            authToken: sessionManagementToken
        )
    }
    
    // MARK: - User Discovery
    
    /// Gets users with a username matching the provided fragment.
    func getUsersMatchingFragment(sessionManagementToken: String, usernameFragment: String) async throws -> Data {
        // This is a GET request, no body, with auth. Fragment is in path.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentUsers, GVOAppConstants.pathSegmenSearch, usernameFragment],
            method: .get,
            authToken: sessionManagementToken
        )
    }
    
    /// Gets the profile details for a user
    func getProfileDetails(sessionManagementToken: String, username: String) async throws -> Data {
        // This is a GET request, no body, with auth. Username is in path.
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentUsers, username, GVOAppConstants.pathSegmenProfile],
            method: .get,
            authToken: sessionManagementToken
        )
    }

    // MARK: - Appeals

    func getHiddenPosts(sessionManagementToken: String, batch: Int) async throws -> Data {
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentAppeals, GVOAppConstants.pathSegmentHidden, GVOAppConstants.pathSegmentPosts, String(batch)],
            method: .get,
            authToken: sessionManagementToken
        )
    }

    func getHiddenComments(sessionManagementToken: String, batch: Int) async throws -> Data {
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentAppeals, GVOAppConstants.pathSegmentHidden, GVOAppConstants.pathSegmentComments, String(batch)],
            method: .get,
            authToken: sessionManagementToken
        )
    }

    func getMyAppeals(sessionManagementToken: String, batch: Int) async throws -> Data {
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentAppeals, GVOAppConstants.pathSegmentMine, String(batch)],
            method: .get,
            authToken: sessionManagementToken
        )
    }

    func submitAppeal(sessionManagementToken: String, targetType: String, targetIdentifier: String, reason: String) async throws -> Data {
        let body = SubmitAppealBody(target_type: targetType, target_identifier: targetIdentifier, reason: reason)
        let requestBody = try encode(body)
        return try await performRequest(
            pathSegments: [GVOAppConstants.pathSegmentAppeals, GVOAppConstants.pathSegmentSubmit],
            method: .post,
            body: requestBody,
            authToken: sessionManagementToken
        )
    }
}
