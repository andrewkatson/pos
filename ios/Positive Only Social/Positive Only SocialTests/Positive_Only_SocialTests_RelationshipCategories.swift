//
//  Positive_Only_SocialTests_RelationshipCategories.swift
//  Positive Only Social
//
//  Relationship categories & post audience (issue #392).
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_RelationshipCategories {

    var stubAPI: StatefulStubbedAPI!

    init() {
        stubAPI = StatefulStubbedAPI()
    }

    private func registerUserAndGetToken(username: String) async throws -> String {
        let data = try await stubAPI.register(
            username: username, email: "\(username)@test.com", password: "123",
            rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        struct RegFields: Decodable { let session_management_token: String }
        return try JSONDecoder().decode(RegFields.self, from: data).session_management_token
    }

    private func profile(_ token: String, of username: String) async throws -> ProfileDetailsResponse {
        let data = try await stubAPI.getProfileDetails(sessionManagementToken: token, username: username)
        return try JSONDecoder().decode(ProfileDetailsResponse.self, from: data)
    }

    private func makePost(_ token: String, caption: String, audience: PostAudience) async throws -> String {
        let data = try await stubAPI.makePost(
            sessionManagementToken: token, imageURL: "image.url/x",
            caption: caption, audience: audience.rawValue)
        return try JSONDecoder().decode(MakePostResponse.self, from: data).postIdentifier
    }

    // MARK: - Categories

    @Test func followWithCategoryIsReflectedOnProfile() async throws {
        _ = try await registerUserAndGetToken(username: "target")
        let viewerToken = try await registerUserAndGetToken(username: "viewer")

        _ = try await stubAPI.followUser(
            sessionManagementToken: viewerToken, username: "target",
            category: FollowCategory.family.rawValue)

        let details = try await profile(viewerToken, of: "target")
        #expect(details.isFollowing == true)
        #expect(details.followCategory == FollowCategory.family.rawValue)
    }

    @Test func followDefaultsToFollowingCategory() async throws {
        _ = try await registerUserAndGetToken(username: "target")
        let viewerToken = try await registerUserAndGetToken(username: "viewer")

        _ = try await stubAPI.followUser(sessionManagementToken: viewerToken, username: "target")

        let details = try await profile(viewerToken, of: "target")
        #expect(details.followCategory == FollowCategory.following.rawValue)
    }

    @Test func setFollowCategoryRequiresAnExistingFollow() async throws {
        _ = try await registerUserAndGetToken(username: "target")
        let viewerToken = try await registerUserAndGetToken(username: "viewer")

        await #expect(throws: (any Error).self) {
            _ = try await stubAPI.setFollowCategory(
                sessionManagementToken: viewerToken, username: "target",
                category: FollowCategory.friend.rawValue)
        }

        _ = try await stubAPI.followUser(sessionManagementToken: viewerToken, username: "target")
        _ = try await stubAPI.setFollowCategory(
            sessionManagementToken: viewerToken, username: "target",
            category: FollowCategory.friend.rawValue)
        let details = try await profile(viewerToken, of: "target")
        #expect(details.followCategory == FollowCategory.friend.rawValue)
    }

    @Test func profileHasNilCategoryWhenNotFollowing() async throws {
        _ = try await registerUserAndGetToken(username: "target")
        let viewerToken = try await registerUserAndGetToken(username: "viewer")

        let details = try await profile(viewerToken, of: "target")
        #expect(details.isFollowing == false)
        #expect(details.followCategory == nil)
    }

    // MARK: - Post audience visibility

    @Test func familyOnlyPostReachesOnlyFamily() async throws {
        let viewerToken = try await registerUserAndGetToken(username: "viewer")
        let authorToken = try await registerUserAndGetToken(username: "author")

        // The author labels the viewer a friend, then posts to family only.
        _ = try await stubAPI.followUser(
            sessionManagementToken: authorToken, username: "viewer",
            category: FollowCategory.friend.rawValue)
        let postId = try await makePost(authorToken, caption: "family news", audience: .family)

        // A friend is too far out for a family-only post.
        await #expect(throws: (any Error).self) {
            _ = try await stubAPI.getPostDetails(sessionManagementToken: viewerToken, postIdentifier: postId)
        }

        // Promote to family and it becomes visible.
        _ = try await stubAPI.setFollowCategory(
            sessionManagementToken: authorToken, username: "viewer",
            category: FollowCategory.family.rawValue)
        let data = try await stubAPI.getPostDetails(sessionManagementToken: viewerToken, postIdentifier: postId)
        let post = try JSONDecoder().decode(Post.self, from: data)
        #expect(post.audience == PostAudience.family.rawValue)
    }

    @Test func authorAlwaysSeesOwnRestrictedPost() async throws {
        let authorToken = try await registerUserAndGetToken(username: "author")
        let postId = try await makePost(authorToken, caption: "just me", audience: .family)

        let data = try await stubAPI.getPostDetails(sessionManagementToken: authorToken, postIdentifier: postId)
        let post = try JSONDecoder().decode(Post.self, from: data)
        #expect(post.audience == PostAudience.family.rawValue)
    }

    // MARK: - Feed group filter

    @Test func followedFeedFiltersByExactGroup() async throws {
        stubAPI.pageSize = 10
        let viewerToken = try await registerUserAndGetToken(username: "viewer")
        let famToken = try await registerUserAndGetToken(username: "famUser")
        let friToken = try await registerUserAndGetToken(username: "friUser")

        _ = try await stubAPI.followUser(
            sessionManagementToken: viewerToken, username: "famUser",
            category: FollowCategory.family.rawValue)
        _ = try await stubAPI.followUser(
            sessionManagementToken: viewerToken, username: "friUser",
            category: FollowCategory.friend.rawValue)

        let famPost = try await makePost(famToken, caption: "fam", audience: .public)
        let friPost = try await makePost(friToken, caption: "fri", audience: .public)

        func feedIds(category: FollowCategory?) async throws -> [String] {
            let data = try await stubAPI.getPostsForFollowedUsers(
                sessionManagementToken: viewerToken, batch: 0, category: category?.rawValue)
            return try JSONDecoder().decode([Post].self, from: data).map { $0.postIdentifier }
        }

        let all = try await feedIds(category: nil)
        #expect(all.contains(famPost))
        #expect(all.contains(friPost))

        let familyOnly = try await feedIds(category: .family)
        #expect(familyOnly == [famPost])

        let friendOnly = try await feedIds(category: .friend)
        #expect(friendOnly == [friPost])
    }
}
