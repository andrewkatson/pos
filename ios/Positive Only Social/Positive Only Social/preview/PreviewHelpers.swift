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

struct MockedAPI: APIProtocol {
    
    // MARK: - Helpers for Double Encoding
    
    // Used for single objects and list items. Includes model/pk to satisfy DjangoLoginResponseObject.
    private struct DjangoSingleResponse<T: Codable>: Codable {
        let model: String
        let pk: Int
        let fields: T
        
        enum CodingKeys: String, CodingKey { case model, pk, fields }
        
        init(model: String = "", pk: Int = 0, fields: T) {
            self.model = model
            self.pk = pk
            self.fields = fields
        }
    }
    
    private struct APIWrapper: Codable {
        let response_list: String
    }
    
    private func encodeSingle<T: Codable>(_ item: T) throws -> Data {
        let djangoObj = DjangoSingleResponse(fields: item)
        let innerData = try JSONEncoder().encode(djangoObj)
        guard let innerString = String(data: innerData, encoding: .utf8) else {
            throw URLError(.cannotDecodeContentData)
        }
        let wrapper = APIWrapper(response_list: innerString)
        return try JSONEncoder().encode(wrapper)
    }
    
    private func encodeList<T: Codable>(_ items: [T]) throws -> Data {
        let djangoList = items.map { DjangoSingleResponse(fields: $0) }
        let innerData = try JSONEncoder().encode(djangoList)
        guard let innerString = String(data: innerData, encoding: .utf8) else {
            throw URLError(.cannotDecodeContentData)
        }
        let wrapper = APIWrapper(response_list: innerString)
        return try JSONEncoder().encode(wrapper)
    }
    
    private func encodeGenericSuccess() throws -> Data {
        let innerString = "{}"
        let wrapper = APIWrapper(response_list: innerString)
        return try JSONEncoder().encode(wrapper)
    }

    // MARK: - User & Session Management

    func register(username: String, email: String, password: String, rememberMe: String, ip: String, dateOfBirth: String) async throws -> Data {
        let response = LoginResponseFields(
            sessionManagementToken: "mock_session_token",
            seriesIdentifier: "mock_series_id",
            loginCookieToken: "mock_login_cookie"
        )
        return try encodeSingle(response)
    }

    func loginUser(usernameOrEmail: String, password: String, rememberMe: String, ip: String) async throws -> Data {
        let response = LoginResponseFields(
            sessionManagementToken: "mock_session_token",
            seriesIdentifier: "mock_series_id",
            loginCookieToken: "mock_login_cookie"
        )
        return try encodeSingle(response)
    }

    func loginUserWithRememberMe(sessionManagementToken: String, seriesIdentifier: String, loginCookieToken: String, ip: String) async throws -> Data {
        let response = LoginResponseFields(
            sessionManagementToken: "new_mock_session",
            seriesIdentifier: "mock_series_id",
            loginCookieToken: "new_mock_cookie"
        )
        return try encodeSingle(response)
    }
    
    func verifyIdentity(sessionManagementToken: String, dateOfBirth: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func resetPassword(username: String, email: String, newPassword: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func requestPasswordReset(usernameOrEmail: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func verifyPasswordReset(usernameOrEmail: String, resetID: Int) async throws -> Data {
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

    func makePost(sessionManagementToken: String, imageURL: String, caption: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func deletePost(sessionManagementToken: String, postIdentifier: String) async throws -> Data {
        return try encodeGenericSuccess()
    }

    func reportPost(sessionManagementToken: String, postIdentifier: String, reason: String) async throws -> Data {
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
            Post(postIdentifier: "1", imageUrl: "https://picsum.photos/400/300", caption: "Beautiful sunset!", authorUsername: "nature_lover"),
            Post(postIdentifier: "2", imageUrl: "https://picsum.photos/400/301", caption: "My new puppy", authorUsername: "dog_fan")
        ]
        return try encodeList(posts)
    }

    func getPostsForFollowedUsers(sessionManagementToken: String, batch: Int) async throws -> Data {
        let posts = [
            Post(postIdentifier: "3", imageUrl: "https://picsum.photos/400/302", caption: "Coffee time", authorUsername: "coffee_addict")
        ]
        return try encodeList(posts)
    }

    func getPostsForUser(sessionManagementToken: String, username: String, batch: Int) async throws -> Data {
        let posts = [
            Post(postIdentifier: "4", imageUrl: "https://picsum.photos/400/303", caption: "Just me", authorUsername: username)
        ]
        return try encodeList(posts)
    }

    func getPostDetails(postIdentifier: String) async throws -> Data {
        // Matches PostDetailViewModel.PostDetailsFields
        struct PostDetailsResponse: Codable {
            let post_identifier: String
            let image_url: String
            let caption: String
            let post_likes: Int
            let author_username: String
        }
        
        let detail = PostDetailsResponse(
            post_identifier: postIdentifier,
            image_url: "https://picsum.photos/400/400",
            caption: "Detailed view of the post",
            post_likes: 100,
            author_username: "mock_author"
        )
        return try encodeSingle(detail)
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

    func getCommentsForPost(postIdentifier: String, batch: Int) async throws -> Data {
        // Matches PostDetailViewModel.ThreadIDFields
        struct ThreadIDResponse: Codable {
            let comment_thread_identifier: String
        }
        
        let threads = [
            ThreadIDResponse(comment_thread_identifier: "thread_1"),
            ThreadIDResponse(comment_thread_identifier: "thread_2")
        ]
        return try encodeList(threads)
    }

    func getCommentsForThread(commentThreadIdentifier: String, batch: Int) async throws -> Data {
        // Matches PostDetailViewModel.CommentFields
        struct CommentResponse: Codable {
            let comment_identifier: String
            let body: String
            let author_username: String
            let comment_creation_time: String
            let comment_updated_time: String
            let comment_likes: Int
        }
        
        let comments = [
            CommentResponse(
                comment_identifier: "c1",
                body: "Great post!",
                author_username: "fan_1",
                comment_creation_time: "2023-01-01T12:00:00Z",
                comment_updated_time: "2023-01-01T12:00:00Z",
                comment_likes: 5
            ),
            CommentResponse(
                comment_identifier: "c2",
                body: "I agree!",
                author_username: "fan_2",
                comment_creation_time: "2023-01-01T12:05:00Z",
                comment_updated_time: "2023-01-01T12:05:00Z",
                comment_likes: 2
            )
        ]
        return try encodeList(comments)
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
        return try encodeList(users)
    }
    
    func getProfileDetails(sessionManagementToken: String, username: String) async throws -> Data {
        let profile = ProfileDetailsResponse(
            username: username,
            postCount: 10,
            followerCount: 100,
            followingCount: 50,
            isFollowing: false
        )
        return try encodeSingle(profile)
    }
}

// MARK: - Preview Helpers

struct PreviewHelpers {
    static let api: APIProtocol = MockedAPI()
    static let keychainHelper: KeychainHelperProtocol = MockKeychainHelper()
    
    @MainActor static var authManager: AuthenticationManager {
        let manager = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychainHelper)
        return manager
    }
    
    @MainActor static func loggedInAuthManager() -> AuthenticationManager {
        let manager = AuthenticationManager(shouldAutoLogin: false, keychainHelper: keychainHelper)
        manager.login(with: UserSession(sessionToken: "mock_token", username: "preview_user", isIdentityVerified: true))
        return manager
    }
}
