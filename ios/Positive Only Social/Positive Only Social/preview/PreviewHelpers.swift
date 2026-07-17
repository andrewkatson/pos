//
//  PreviewHelpers.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/7/25.
//

import Foundation
import SwiftUI

// MARK: - Mock Keychain Helper

class MockKeychainHelper: KeychainHelperProtocol {
    private var storage: [String: Data] = [:]
    
    func save<T: Codable>(_ value: T, for service: String, account: String) throws {
        let key = "\(service):\(account)"
        let data = try JSONEncoder().encode(value)
        storage[key] = data
    }
    
    func load<T: Codable>(_ type: T.Type, from service: String, account: String) throws -> T? {
        let key = "\(service):\(account)"
        guard let data = storage[key] else { return nil }
        return try JSONDecoder().decode(T.self, from: data)
    }
    
    func delete(service: String, account: String) throws {
        let key = "\(service):\(account)"
        storage.removeValue(forKey: key)
    }
}

// MARK: - Mocked API

struct MockedAPI: Networking {
    private let previewS3Bucket = "https://example-bucket.s3.us-east-2.amazonaws.com/"

    // MARK: - Encoding Helpers

    private func encode<T: Encodable>(_ value: T) throws -> Data {
        return try JSONEncoder().encode(value)
    }

    private func encodeGenericSuccess() throws -> Data {
        return try JSONEncoder().encode(["message": "ok"])
    }

    // MARK: - User & Session Management

    func register(username: String, email: String, password: String, rememberMe: String, ip: String, dateOfBirth: String) async throws -> Data {
        let response = LoginResponseFields(
            sessionManagementToken: "mock_session_token",
            username: username,
            userId: "00000000-0000-0000-0000-000000000001",
            seriesIdentifier: "mock_series_id",
            loginCookieToken: "mock_login_cookie"
        )
        return try encode(response)
    }

    func loginUser(usernameOrEmail: String, password: String, rememberMe: String, ip: String) async throws -> Data {
        let response = LoginResponseFields(
            sessionManagementToken: "mock_session_token",
            username: usernameOrEmail,
            userId: "00000000-0000-0000-0000-000000000001",
            seriesIdentifier: "mock_series_id",
            loginCookieToken: "mock_login_cookie"
        )
        return try encode(response)
    }

    func loginUserWithRememberMe(sessionManagementToken: String, seriesIdentifier: String, loginCookieToken: String, ip: String) async throws -> Data {
        let response = LoginResponseFields(
            sessionManagementToken: "new_mock_session",
            username: "mock_user",
            userId: "00000000-0000-0000-0000-000000000001",
            seriesIdentifier: "mock_series_id",
            loginCookieToken: "new_mock_cookie"
        )
        return try encode(response)
    }
    
    func verifyIdentity(sessionManagementToken: String, dateOfBirth: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func resetPassword(username: String, email: String, newPassword: String, resetToken: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func requestPasswordReset(usernameOrEmail: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func verifyPasswordReset(usernameOrEmail: String, verificationToken: String) async throws -> Data {
        return try encode(["message": "ok", "reset_token": "preview_reset_token"])
    }

    func verifyEmail(verificationToken: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func resendVerificationEmail(usernameOrEmail: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func logoutUser(sessionManagementToken: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func deleteUser(sessionManagementToken: String) async throws -> Data {
        return try encodeGenericSuccess()
    }
    
    func followUser(sessionManagementToken: String, username: String) async throws -> Data {
        return try encodeGenericSuccess()
    }
    
    func unfollowUser(sessionManagementToken: String, username: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func toggleBlock(sessionManagementToken: String, username: String) async throws -> Data {
        return try encodeGenericSuccess()
    }
    
    // MARK: - Post Management

    func createUploadUrl(sessionManagementToken: String) async throws -> Data {
        let imageUrl = "\(previewS3Bucket)preview-user/preview.jpeg"
        let response = UploadUrlResponse(
            uploadUrl: "\(imageUrl)?X-Amz-Signature=preview",
            imageUrl: imageUrl
        )
        return try JSONEncoder().encode(response)
    }

    func makePost(sessionManagementToken: String, imageURL: String?, caption: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func deletePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func reportPost(sessionManagementToken: String, postIdentifier: String, reason: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func retractReportPost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func likePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func unlikePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func getPostsInFeed(sessionManagementToken: String, batch: Int) async throws -> Data {
        let posts = [
            Post(postIdentifier: "1", imageUrl: "https://picsum.photos/400/300", originalImageUrl: nil, caption: "Beautiful sunset!", authorUsername: "nature_lover"),
            Post(postIdentifier: "2", imageUrl: "https://picsum.photos/400/301", originalImageUrl: nil, caption: "My new puppy", authorUsername: "dog_fan"),
            // A text-only post (#307) so previews exercise the caption tile.
            Post(postIdentifier: "5", imageUrl: nil, originalImageUrl: nil, caption: "Words only today — feeling grateful!", authorUsername: "text_poster")
        ]
        return try encode(posts)
    }

    func getPostsForFollowedUsers(sessionManagementToken: String, batch: Int) async throws -> Data {
        let posts = [
            Post(postIdentifier: "3", imageUrl: "https://picsum.photos/400/302", originalImageUrl: nil, caption: "Coffee time", authorUsername: "coffee_addict")
        ]
        return try encode(posts)
    }

    func getPostsForUser(sessionManagementToken: String, username: String, batch: Int) async throws -> Data {
        let posts = [
            Post(postIdentifier: "4", imageUrl: "https://picsum.photos/400/303", originalImageUrl: nil, caption: "Just me", authorUsername: username)
        ]
        return try encode(posts)
    }

    func getPostDetails(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        // Matches PostDetailViewModel.PostDetailsFields
        struct PostDetailsResponse: Codable {
            let post_identifier: String
            let image_url: String
            let caption: String
            //TODO: eBlender rename to camelCase creationTime (via CodingKeys).
            let creation_time: String
            let post_likes: Int
            let is_liked: Bool
            let author_username: String
        }

        let detail = PostDetailsResponse(
            post_identifier: postIdentifier,
            image_url: "https://picsum.photos/400/400",
            caption: "Detailed view of the post",
            creation_time: ISO8601DateFormatter().string(from: Date().addingTimeInterval(-2 * 60 * 60)),
            post_likes: 100,
            is_liked: false,
            author_username: "mock_author"
        )
        return try encode(detail)
    }
    
    // MARK: - Comment Management

    func commentOnPost(sessionManagementToken: String, postIdentifier: String, commentText: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func likeComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func unlikeComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func deleteComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func reportComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String, reason: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func retractReportComment(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentIdentifier: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func getCommentsForPost(sessionManagementToken: String, postIdentifier: String, batch: Int) async throws -> Data {
        // Matches PostDetailViewModel.ThreadIDFields
        struct ThreadIDResponse: Codable {
            let comment_thread_identifier: String
        }
        
        let threads = [
            ThreadIDResponse(comment_thread_identifier: "thread_1"),
            ThreadIDResponse(comment_thread_identifier: "thread_2")
        ]
        return try encode(threads)
    }

    func getCommentsForThread(sessionManagementToken: String, commentThreadIdentifier: String, batch: Int) async throws -> Data {
        // Matches PostDetailViewModel.CommentFields
        struct CommentResponse: Codable {
            let comment_identifier: String
            let body: String
            let author_username: String
            let creation_time: String
            let updated_time: String
            let comment_likes: Int
            let is_liked: Bool
        }

        let comments = [
            CommentResponse(
                comment_identifier: "c1",
                body: "Great post!",
                author_username: "fan_1",
                creation_time: "2023-01-01T12:00:00Z",
                updated_time: "2023-01-01T12:00:00Z",
                comment_likes: 5,
                is_liked: false
            ),
            CommentResponse(
                comment_identifier: "c2",
                body: "I agree!",
                author_username: "fan_2",
                creation_time: "2023-01-01T12:05:00Z",
                updated_time: "2023-01-01T12:05:00Z",
                comment_likes: 2,
                is_liked: true
            )
        ]
        return try encode(comments)
    }

    func replyToCommentThread(sessionManagementToken: String, postIdentifier: String, commentThreadIdentifier: String, commentText: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    // MARK: - User Discovery

    func getUsersMatchingFragment(sessionManagementToken: String, usernameFragment: String) async throws -> Data {
        let users = [
            User(username: "search_result_1", identityIsVerified: true),
            User(username: "search_result_2", identityIsVerified: false)
        ]
        return try encode(users)
    }
    
    func getProfileDetails(sessionManagementToken: String, username: String) async throws -> Data {
        let profile = ProfileDetailsResponse(
            username: username,
            postCount: 10,
            followerCount: 100,
            followingCount: 50,
            isFollowing: false
        )
        return try encode(profile)
    }

    // MARK: - Appeals

    func getHiddenPosts(sessionManagementToken: String, batch: Int) async throws -> Data {
        return try encode([HiddenPost]())
    }

    func getHiddenComments(sessionManagementToken: String, batch: Int) async throws -> Data {
        return try encode([HiddenComment]())
    }

    func getMyAppeals(sessionManagementToken: String, batch: Int) async throws -> Data {
        return try encode([MyAppeal]())
    }

    func submitAppeal(sessionManagementToken: String, targetType: String, targetIdentifier: String, reason: String) async throws -> Data {
        struct Fields: Codable { let appeal_identifier: String }
        return try encode(Fields(appeal_identifier: UUID().uuidString))
    }
}

// MARK: - Preview Helpers

struct PreviewHelpers {
    static let api: Networking = MockedAPI()
    static let keychainHelper: KeychainHelperProtocol = MockKeychainHelper()
    
    @MainActor static var authManager: AuthenticationManager {
        let manager = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychainHelper)
        return manager
    }
    
    @MainActor static let loggedInAuthManager: AuthenticationManager = {
        let manager = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychainHelper)
        manager.login(with: UserSession(sessionToken: "mock_token", username: "preview_user", userId: "00000000-0000-0000-0000-000000000001", isIdentityVerified: true))
        return manager
    }()
}
