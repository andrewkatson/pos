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
        }
    }
}

// MARK: - Real API Implementation
/// A concrete class that implements the APIProtocol to make live network requests.
final class RealAPI: APIProtocol {

    /// The base URL for all API endpoints. Remember to replace this with your actual server address.
    private let baseURL = "https://your.api.backend.com/"

    // MARK: - Private Helper
    
    /// A generic helper function to perform a network request.
    /// - Parameter pathSegments: The components of the URL path that will be joined by `/`.
    /// - Returns: The raw `Data` from the server response.
    /// - Throws: An `APIError` if the request fails at any stage.
    private func performRequest(pathSegments: [String]) async throws -> Data {
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
        
        // NOTE: In a production REST API, operations that change data on the server
        // (e.g., register, makePost, deletePost) should use appropriate HTTP methods
        // like POST, PUT, PATCH, or DELETE, often with a JSON body.
        // The current implementation uses GET for all, as implied by the urlpatterns.
        let request = URLRequest(url: url)

        // 2. Perform the network call
        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            // 3. Validate the HTTP response
            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.badServerResponse(statusCode: -1) // Should not happen with HTTP/S
            }

            guard (200...299).contains(httpResponse.statusCode) else {
                throw APIError.badServerResponse(statusCode: httpResponse.statusCode)
            }
            
            // 4. Return the response data
            return data
        } catch let error as APIError {
            throw error // Re-throw our specific API errors
        } catch {
            throw APIError.requestFailed(error) // Wrap other errors
        }
    }
    
    // MARK: - User & Session Management

    /// Creates a user if they do not exist.
    func register(username: String, email: String, password: String, rememberMe: String, ip: String) async throws -> Data {
        return try await performRequest(pathSegments: ["register", username, email, password, rememberMe, ip])
    }

    /// Logs the user in if they exist.
    func loginUser(usernameOrEmail: String, password: String, rememberMe: String, ip: String) async throws -> Data {
        return try await performRequest(pathSegments: ["login_user", usernameOrEmail, password, rememberMe, ip])
    }

    /// Logs the user in using a "remember me" token.
    func loginUserWithRememberMe(sessionManagementToken: String, seriesIdentifier: String, loginCookieToken: String, ip: String) async throws -> Data {
        return try await performRequest(pathSegments: ["login_user_with_remember_me", sessionManagementToken, seriesIdentifier, loginCookieToken, ip])
    }

    /// Resets the user's password.
    func resetPassword(username: String, email: String, newPassword: String) async throws -> Data {
        return try await performRequest(pathSegments: ["reset_password", username, email, newPassword])
    }

    /// Requests a password reset and sends the user an email.
    func requestPasswordReset(usernameOrEmail: String) async throws -> Data {
        return try await performRequest(pathSegments: ["request_reset", usernameOrEmail])
    }

    /// Verifies the password reset identifier.
    func verifyPasswordReset(usernameOrEmail: String, resetID: Int) async throws -> Data {
        return try await performRequest(pathSegments: ["verify_reset", usernameOrEmail, String(resetID)])
    }

    /// Logs the user out.
    func logoutUser(sessionManagementToken: String) async throws -> Data {
        return try await performRequest(pathSegments: ["logout_user", sessionManagementToken])
    }

    /// Deletes the user account.
    func deleteUser(sessionManagementToken: String) async throws -> Data {
        return try await performRequest(pathSegments: ["delete_user", sessionManagementToken])
    }

    // MARK: - Post Management

    /// Creates and stores a new post.
    func makePost(sessionManagementToken: String, imageURL: String, caption: String) async throws -> Data {
        return try await performRequest(pathSegments: ["make_post", sessionManagementToken, imageURL, caption])
    }

    /// Deletes a post.
    func deletePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        return try await performRequest(pathSegments: ["delete_post", sessionManagementToken, postIdentifier])
    }

    /// Reports a post for a specific reason.
    func reportPost(sessionManagementToken: String, postIdentifier: String, reason: String) async throws -> Data {
        return try await performRequest(pathSegments: ["report_post", sessionManagementToken, postIdentifier, reason])
    }

    /// Likes a post.
    func likePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        return try await performRequest(pathSegments: ["like_post", sessionManagementToken, postIdentifier])
    }

    /// Unlikes a post.
    func unlikePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        return try await performRequest(pathSegments: ["unlike_post", sessionManagementToken, postIdentifier])
    }

    /// Gets all posts for the user's feed in batches.
    func getPostsInFeed(sessionManagementToken: String, batch: Int) async throws -> Data {
        return try await performRequest(pathSegments: ["get_posts_in_feed", sessionManagementToken, String(batch)])
    }

    /// Gets a batch of posts for another user.
    func getPostsForUser(sessionManagementToken: String, username: String, batch: Int) async throws -> Data {
        return try await performRequest(pathSegments: ["get_posts_for_user", sessionManagementToken, username, String(batch)])
    }

    /// Gets the details for a single post.
    func getPostDetails(postIdentifier: String) async throws -> Data {
        return try await performRequest(pathSegments: ["get_post_details", postIdentifier])
    }

    // MARK: - Comment Management

    /// Adds a direct comment to a post.
    func commentOnPost(sessionManagementToken: String, postIdentifier: String, commentText: String) async throws -> Data {
        return try await performRequest(pathSegments: ["comment_on_post", sessionManagementToken, postIdentifier, commentText])
    }

    /// Likes a specific comment within a post.
    func likeComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        return try await performRequest(pathSegments: ["like_comment", sessionManagementToken, postIdentifier, commentThreadIdentifier, commentIdentifier])
    }

    /// Unlikes a specific comment.
    func unlikeComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        return try await performRequest(pathSegments: ["unlike_comment", sessionManagementToken, postIdentifier, commentThreadIdentifier, commentIdentifier])
    }

    /// Deletes a comment.
    func deleteComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        return try await performRequest(pathSegments: ["delete_comment", sessionManagementToken, postIdentifier, commentThreadIdentifier, commentIdentifier])
    }

    /// Reports a comment for a specific reason.
    func reportComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String, reason: String) async throws -> Data {
        return try await performRequest(pathSegments: ["report_comment", sessionManagementToken, postIdentifier, commentThreadIdentifier, commentIdentifier, reason])
    }

    /// Gets a batch of comments for a post.
    func getCommentsForPost(postIdentifier: String, batch: Int) async throws -> Data {
        return try await performRequest(pathSegments: ["get_comments_for_post", postIdentifier, String(batch)])
    }

    /// Gets a batch of comments for a specific comment thread.
    func getCommentsForThread(commentThreadIdentifier: String, batch: Int) async throws -> Data {
        return try await performRequest(pathSegments: ["get_comments_for_thread", commentThreadIdentifier, String(batch)])
    }

    /// Replies to a comment thread.
    func replyToCommentThread(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentText: String) async throws -> Data {
        return try await performRequest(pathSegments: ["reply_to_comment_thread", sessionManagementToken, postIdentifier, commentThreadIdentifier, commentText])
    }

    // MARK: - User Discovery

    /// Gets users with a username matching the provided fragment.
    func getUsersMatchingFragment(sessionManagementToken: String, usernameFragment: String) async throws -> Data {
        return try await performRequest(pathSegments: ["get_users_matching_fragment", sessionManagementToken, usernameFragment])
    }
}
