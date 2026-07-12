//
//  Networking.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/5/25.
//

import Foundation

/// A protocol defining the network service layer for the API.
///
/// Each method corresponds to a specific endpoint and is designed to be asynchronous,
/// throwing an error if the network request fails.
protocol Networking {

    // MARK: - User & Session Management

    /// Creates a user if they do not exist.
    func register(username: String, email: String, password: String, rememberMe: String, ip: String, dateOfBirth: String) async throws -> Data

    /// Logs the user in if they exist.
    func loginUser(usernameOrEmail: String, password: String, rememberMe: String, ip: String) async throws -> Data

    /// Logs the user in using a "remember me" token.
    /// This is used if the user's series identifier and login cookie token exist and match what is on record.
    func loginUserWithRememberMe(sessionManagementToken: String, seriesIdentifier: String, loginCookieToken: String, ip: String) async throws -> Data

    /// Resets the user's password. Requires a reset token issued by verifyPasswordReset.
    func resetPassword(username: String, email: String, newPassword: String, resetToken: String) async throws -> Data

    /// Requests a password reset and sends the user an email with instructions.
    func requestPasswordReset(usernameOrEmail: String) async throws -> Data

    /// Verifies the password reset by submitting the opaque verification token received via email.
    func verifyPasswordReset(usernameOrEmail: String, verificationToken: String) async throws -> Data

    /// Verifies the account's email address by submitting the token from the
    /// verification link in the welcome email. Until this succeeds, login and
    /// every authenticated endpoint reject the account with `email_not_verified`.
    func verifyEmail(verificationToken: String) async throws -> Data

    /// Sends a fresh email-verification link, invalidating the previous one.
    func resendVerificationEmail(usernameOrEmail: String) async throws -> Data

    func logoutUser(sessionManagementToken: String) async throws -> Data

    /// Deletes the user account.
    func deleteUser(sessionManagementToken: String) async throws -> Data
    
    /// Verifies the identity of the user
    func verifyIdentity(sessionManagementToken: String, dateOfBirth: String) async throws -> Data
    
    /// Follow a user
    func followUser(sessionManagementToken: String, username: String) async throws -> Data
    
    /// Unfollow a user
    func unfollowUser(sessionManagementToken: String, username: String) async throws -> Data
    
    /// Block or unblock a user
    func toggleBlock(sessionManagementToken: String, username: String) async throws -> Data
    
    // MARK: - Post Management

    /// Requests a backend-issued presigned S3 PUT URL for a new post image
    /// (the backend scopes the object key to the authenticated user).
    func createUploadUrl(sessionManagementToken: String) async throws -> Data

    /// Creates and stores a new post. A nil `imageURL` creates a text-only post (#307).
    func makePost(sessionManagementToken: String, imageURL: String?, caption: String) async throws -> Data

    /// Deletes a post.
    func deletePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data

    /// Reports a post for a specific reason.
    func reportPost(sessionManagementToken: String, postIdentifier: String, reason: String) async throws -> Data

    /// Retracts the current user's report against a post (issue #176).
    func retractReportPost(sessionManagementToken: String, postIdentifier: String) async throws -> Data

    /// Likes a post.
    func likePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data

    /// Unlikes a post.
    func unlikePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data

    /// Gets all posts for the user's feed in batches.
    func getPostsInFeed(sessionManagementToken: String, batch: Int) async throws -> Data

    /// Get all posts for a user's feed in batches for anyone they follow.
    func getPostsForFollowedUsers(sessionManagementToken: String, batch: Int) async throws -> Data

    /// Gets a batch of posts for another user.
    func getPostsForUser(sessionManagementToken: String, username: String, batch: Int) async throws -> Data

    /// Gets the details for a single post. Requires auth so the response can
    /// include whether the current user has liked the post.
    func getPostDetails(sessionManagementToken: String, postIdentifier: String) async throws -> Data
    
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

    /// Retracts the current user's report against a comment (issue #176).
    func retractReportComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data

    /// Gets a batch of comment threads for a post. Requires auth.
    func getCommentsForPost(sessionManagementToken: String, postIdentifier: String, batch: Int) async throws -> Data

    /// Gets a batch of comments for a specific comment thread (i.e., replies to a comment).
    /// Requires auth so each comment can include whether the current user has liked it.
    func getCommentsForThread(sessionManagementToken: String, commentThreadIdentifier: String, batch: Int) async throws -> Data

    /// Replies to a comment thread.
    func replyToCommentThread(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentText: String) async throws -> Data

    // MARK: - User Discovery

    /// Gets users with a username matching the provided fragment.
    func getUsersMatchingFragment(sessionManagementToken: String, usernameFragment: String) async throws -> Data
    
    /// Gets the details of a profile
    func getProfileDetails(sessionManagementToken: String, username: String) async throws -> Data

    // MARK: - Appeals

    /// Gets a batch of the signed-in user's own hidden posts.
    func getHiddenPosts(sessionManagementToken: String, batch: Int) async throws -> Data

    /// Gets a batch of the signed-in user's own hidden comments.
    func getHiddenComments(sessionManagementToken: String, batch: Int) async throws -> Data

    /// Gets a batch of the appeals the signed-in user has filed.
    func getMyAppeals(sessionManagementToken: String, batch: Int) async throws -> Data

    /// Files an appeal against a hidden post or comment. `targetType` is
    /// "post" or "comment"; ban appeals go through the email-reply flow.
    func submitAppeal(sessionManagementToken: String, targetType: String, targetIdentifier: String, reason: String) async throws -> Data
}
