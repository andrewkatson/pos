//
//  RealAPI.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/5/25.
//

import Foundation

// MARK: - API Error Definition
/// Defines specific errors that can occur during an API call.
enum APIError: Error, LocalizedError {
    case invalidURL
    case badServerResponse(statusCode: Int)
    case requestFailed(Error)
    case decodingError(Error)
    case encodingError(Error) // Added for JSON encoding failures

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "The URL provided was invalid."
        case .badServerResponse(let statusCode):
            return "The server returned an unsuccessful status code: \(statusCode)."
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
final class RealAPI: APIProtocol {

    /// The base URL for all API endpoints. Remember to replace this with your actual server address.
    private let baseURL = "https://smiling.social/"
    
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
    }
    
    private struct RequestResetBody: Encodable {
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
        let path = pathSegments.map {
            // Ensure each path component is properly encoded
            $0.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? ""
        }.joined(separator: "/")
        
        urlComponents?.path = "/" + path

        guard let url = urlComponents?.url else {
            throw APIError.invalidURL
        }
        
        // 2. Create the request and set the method
        var request = URLRequest(url: url)
        request.httpMethod = method.rawValue

        // 3. Add Headers
        if let authToken = authToken {
            request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        }
        
        // 4. Add Body
        if let body = body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }

        // 5. Perform the network call
        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            // 6. Validate the HTTP response
            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.badServerResponse(statusCode: -1) // Should not happen with HTTP/S
            }

            guard (200...299).contains(httpResponse.statusCode) else {
                // You could try to decode an error JSON body here if your API sends one
                // let errorBody = String(data: data, encoding: .utf8)
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
            pathSegments: ["register"],
            method: .post,
            body: requestBody
        )
    }

    /// Logs the user in if they exist.
    func loginUser(usernameOrEmail: String, password: String, rememberMe: String, ip: String) async throws -> Data {
        let body = LoginBody(username_or_email: usernameOrEmail, password: password, remember_me: rememberMe, ip: ip)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: ["login_user"],
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
            pathSegments: ["login_user_with_remember_me"],
            method: .post,
            body: requestBody
        )
    }

    /// Resets the user's password.
    func resetPassword(username: String, email: String, newPassword: String) async throws -> Data {
        let body = ResetPasswordBody(username: username, email: email, password: newPassword)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: ["reset_password"],
            method: .post,
            body: requestBody
        )
    }

    /// Requests a password reset and sends the user an email.
    func requestPasswordReset(usernameOrEmail: String) async throws -> Data {
        let body = RequestResetBody(username_or_email: usernameOrEmail)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: ["request_reset"],
            method: .post,
            body: requestBody
        )
    }

    /// Verifies the password reset identifier.
    func verifyPasswordReset(usernameOrEmail: String, resetID: Int) async throws -> Data {
        // This is a GET request, no body or auth.
        return try await performRequest(
            pathSegments: ["verify_reset", usernameOrEmail, String(resetID)],
            method: .get
        )
    }

    /// Logs the user out.
    func logoutUser(sessionManagementToken: String) async throws -> Data {
        // This is a POST request, no body, with auth.
        return try await performRequest(
            pathSegments: ["logout_user"],
            method: .post,
            authToken: sessionManagementToken
        )
    }
    
    /// Deletes the user account.
    func deleteUser(sessionManagementToken: String) async throws -> Data {
        // This is a POST request, no body, with auth.
        return try await performRequest(
            pathSegments: ["delete_user"],
            method: .post,
            authToken: sessionManagementToken
        )

    
    /// Verifies the identity of the user
    func verifyIdentity(sessionManagementToken: String, dateOfBirth: String) async throws -> Data {
        let body = VerifyIdentityBody(date_of_birth: dateOfBirth)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: ["verify-identity"],
            method: .post,
            body: requestBody,
            authToken: sessionManagementToken
        )
    }
    
    /// Follow a user
    func followUser(sessionManagementToken: String, username: String) async throws -> Data {
        // This is a POST request, no body, with auth. Username is in path.
        return try await performRequest(
            pathSegments: ["follow_user", username],
            method: .post,
            authToken: sessionManagementToken
        )
    }

    /// Unfollow a user
    func unfollowUser(sessionManagementToken: String, username: String) async throws -> Data {
        // This is a POST request, no body, with auth. Username is in path.
        return try await performRequest(
            pathSegments: ["unfollow_user", username],
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
            pathSegments: ["users", username, "block"],
            method: .post,
            authToken: sessionManagementToken
        )
    }

    // MARK: - Post Management

    /// Creates and stores a new post.
    func makePost(sessionManagementToken: String, imageURL: String, caption: String) async throws -> Data {
        let body = MakePostBody(image_url: imageURL, caption: caption)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: ["make_post"],
            method: .post,
            body: requestBody,
            authToken: sessionManagementToken
        )
    }

    /// Deletes a post.
    func deletePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        // This is a POST request, no body, with auth. ID is in path.
        return try await performRequest(
            pathSegments: ["delete_post", postIdentifier],
            method: .post,
            authToken: sessionManagementToken
        )
    }

    /// Reports a post for a specific reason.
    func reportPost(sessionManagementToken: String, postIdentifier: String, reason: String) async throws -> Data {
        let body = ReportBody(reason: reason)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: ["report_post", postIdentifier],
            method: .post,
            body: requestBody,
            authToken: sessionManagementToken
        )
    }

    /// Likes a post.
    func likePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        // This is a POST request, no body, with auth. ID is in path.
        return try await performRequest(
            pathSegments: ["like_post", postIdentifier],
            method: .post,
            authToken: sessionManagementToken
        )
    }

    /// Unlikes a post.
    func unlikePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        // This is a POST request, no body, with auth. ID is in path.
        return try await performRequest(
            pathSegments: ["unlike_post", postIdentifier],
            method: .post,
            authToken: sessionManagementToken
        )
    }

    /// Gets all posts for the user's feed in batches.
    func getPostsInFeed(sessionManagementToken: String, batch: Int) async throws -> Data {
        // This is a GET request, no body, with auth. Batch is in path.
        return try await performRequest(
            pathSegments: ["get_posts_in_feed", String(batch)],
            method: .get,
            authToken: sessionManagementToken
        )
    }

        /// Get all posts for a user's feed in batches for anyone they follow.
    func getPostsForFollowedUsers(sessionManagementToken: String, batch: Int) async throws -> Data {
        // This is a GET request, no body, with auth. Batch is in path.
        return try await performRequest(
            pathSegments: ["get_posts_for_followed_users", String(batch)],
            method: .get,
            authToken: sessionManagementToken
        )
    }


    /// Gets a batch of posts for another user.
    func getPostsForUser(sessionManagementToken: String, username: String, batch: Int) async throws -> Data {
        // This is a GET request, no body, with auth. Username/Batch are in path.
        return try await performRequest(
            pathSegments: ["get_posts_for_user", username, String(batch)],
            method: .get,
            authToken: sessionManagementToken
        )
    }

    /// Gets the details for a single post.
    func getPostDetails(postIdentifier: String) async throws -> Data {
        // This is a public GET request, no body, no auth. ID is in path.
        return try await performRequest(
            pathSegments: ["get_post_details", postIdentifier],
            method: .get
        )
    }

    // MARK: - Comment Management

    /// Adds a direct comment to a post.
    func commentOnPost(sessionManagementToken: String, postIdentifier: String, commentText: String) async throws -> Data {
        let body = CommentBody(comment_text: commentText)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: ["comment_on_post", postIdentifier],
            method: .post,
            body: requestBody,
            authToken: sessionManagementToken
        )
    }

    /// Likes a specific comment within a post.
    func likeComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        // This is a POST request, no body, with auth. IDs are in path.
        return try await performRequest(
            pathSegments: ["like_comment", postIdentifier, commentThreadIdentifier, commentIdentifier],
            method: .post,
            authToken: sessionManagementToken
        )
    }

    /// Unlikes a specific comment.
    func unlikeComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        // This is a POST request, no body, with auth. IDs are in path.
        return try await performRequest(
            pathSegments: ["unlike_comment", postIdentifier, commentThreadIdentifier, commentIdentifier],
            method: .post,
            authToken: sessionManagementToken
        )
    }

    /// Deletes a comment.
    func deleteComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        // This is a POST request, no body, with auth. IDs are in path.
        return try await performRequest(
            pathSegments: ["delete_comment", postIdentifier, commentThreadIdentifier, commentIdentifier],
            method: .post,
            authToken: sessionManagementToken
        )
    }

    /// Reports a comment for a specific reason.
    func reportComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String, reason: String) async throws -> Data {
        let body = ReportBody(reason: reason)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: ["report_comment", postIdentifier, commentThreadIdentifier, commentIdentifier],
            method: .post,
            body: requestBody,
            authToken: sessionManagementToken
        )
    }

    /// Gets a batch of comments for a post.
    func getCommentsForPost(postIdentifier: String, batch: Int) async throws -> Data {
        // This is a GET request, no body, with no auth. ID/Batch are in path.
        return try await performRequest(
            pathSegments: ["get_comments_for_post", postIdentifier, String(batch)],
            method: .get,
        )
    }

    /// Gets a batch of comments for a specific comment thread.
    func getCommentsForThread(commentThreadIdentifier: String, batch: Int) async throws -> Data {
        // This is a GET request, no body, with no auth. ID/Batch are in path.
        return try await performRequest(
            pathSegments: ["get_comments_for_thread", commentThreadIdentifier, String(batch)],
            method: .get,
        )
    }

    /// Replies to a comment thread.
    func replyToCommentThread(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentText: String) async throws -> Data {
        let body = CommentBody(comment_text: commentText)
        let requestBody = try encode(body)
        
        return try await performRequest(
            pathSegments: ["reply_to_comment_thread", postIdentifier, commentThreadIdentifier],
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
            pathSegments: ["get_users_matching_fragment", usernameFragment],
            method: .get,
            authToken: sessionManagementToken
        )
    }
    
    /// Gets the profile details for a user
    func getProfileDetails(sessionManagementToken: String, username: String) async throws -> Data {
        // This is a GET request, no body, with auth. Username is in path.
        return try await performRequest(
            pathSegments: ["get_profile_details", username],
            method: .get,
            authToken: sessionManagementToken
        )
    }
}
