//
//  API.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/5/25.
//

import Foundation

/// A protocol defining the network service layer for the API.
///
/// Each method corresponds to a specific endpoint and is designed to be asynchronous,
/// throwing an error if the network request fails.
protocol APIProtocol {

    // MARK: - User & Session Management

    /// Creates a user if they do not exist.
    func register(username: String, email: String, password: String, rememberMe: String, ip: String) async throws -> Data

    /// Logs the user in if they exist.
    func loginUser(usernameOrEmail: String, password: String, rememberMe: String, ip: String) async throws -> Data

    /// Logs the user in using a "remember me" token.
    /// This is used if the user's series identifier and login cookie token exist and match what is on record.
    func loginUserWithRememberMe(sessionManagementToken: String, seriesIdentifier: String, loginCookieToken: String, ip: String) async throws -> Data

    /// Resets the user's password. Assumes the new password has already been confirmed by the user.
    func resetPassword(username: String, email: String, newPassword: String) async throws -> Data

    /// Requests a password reset and sends the user an email with instructions.
    func requestPasswordReset(usernameOrEmail: String) async throws -> Data

    /// Verifies the password reset by checking that the reset identifier matches the one sent in the email.
    func verifyPasswordReset(usernameOrEmail: String, resetID: Int) async throws -> Data

    /// Logs the user out.
    func logoutUser(sessionManagementToken: String) async throws -> Data

    /// Deletes the user account.
    func deleteUser(sessionManagementToken: String) async throws -> Data
    
    /// Follow a user
    func followUser(sessionManagementToken: String, username: String) async throws -> Data
    
    /// Unfollow a user
    func unfollowUser(sessionManagementToken: String, username: String) async throws -> Data
    
    // MARK: - Post Management

    /// Creates and stores a new post.
    func makePost(sessionManagementToken: String, imageURL: String, caption: String) async throws -> Data

    /// Deletes a post.
    func deletePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data

    /// Reports a post for a specific reason.
    func reportPost(sessionManagementToken: String, postIdentifier: String, reason: String) async throws -> Data

    /// Likes a post.
    func likePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data

    /// Unlikes a post.
    func unlikePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data

    /// Gets all posts for the user's feed in batches.
    func getPostsInFeed(sessionManagementToken: String, batch: Int) async throws -> Data

    /// Gets a batch of posts for another user.
    func getPostsForUser(sessionManagementToken: String, username: String, batch: Int) async throws -> Data

    /// Gets the details for a single post.
    func getPostDetails(postIdentifier: String) async throws -> Data
    
    // MARK: - Comment Management

    /// Adds a direct comment to a post.
    func commentOnPost(sessionManagementToken: String, postIdentifier: String, commentText: String) async throws -> Data

    /// Likes a specific comment within a post.
    func likeComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data

    /// Unlikes a specific comment.
    /// Note: Corrected a typo from the original URL pattern `/str:comment_identifier` to `/<str:comment_identifier>`.
    func unlikeComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data

    /// Deletes a comment.
    func deleteComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data

    /// Reports a comment for a specific reason.
    func reportComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String, reason: String) async throws -> Data

    /// Gets a batch of comments for a post.
    func getCommentsForPost(postIdentifier: String, batch: Int) async throws -> Data

    /// Gets a batch of comments for a specific comment thread (i.e., replies to a comment).
    func getCommentsForThread(commentThreadIdentifier: String, batch: Int) async throws -> Data

    /// Replies to a comment thread.
    func replyToCommentThread(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentText: String) async throws -> Data

    // MARK: - User Discovery

    /// Gets users with a username matching the provided fragment.
    func getUsersMatchingFragment(sessionManagementToken: String, usernameFragment: String) async throws -> Data
    
    /// Gets the details of a profile
    func getProfileDetails(sessionManagementToken: String, username: String) async throws -> Data
}
