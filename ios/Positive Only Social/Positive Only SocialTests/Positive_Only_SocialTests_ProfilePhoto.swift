//
//  Positive_Only_SocialTests_ProfilePhoto.swift
//  Positive Only Social
//
//  Profile photo feature (issue #7): exercises the StatefulStubbedAPI's photo
//  set/remove behavior and that the avatar is threaded through the serialized
//  profile, feed, and comment payloads.
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_ProfilePhoto {

    var stub: StatefulStubbedAPI!

    init() {
        stub = StatefulStubbedAPI()
    }

    // MARK: - Helpers

    /// Registers a user and returns their session token.
    private func registerUser(_ username: String) async throws -> String {
        let data = try await stub.register(
            username: username, email: "\(username)@test.com", password: "pw",
            rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        struct RegFields: Decodable { let session_management_token: String }
        return try JSONDecoder().decode(RegFields.self, from: data).session_management_token
    }

    private func makePost(_ token: String, caption: String) async throws -> String {
        let data = try await stub.makePost(sessionManagementToken: token, imageURL: "https://img/\(UUID().uuidString).jpeg", caption: caption)
        return try JSONDecoder().decode(MakePostResponse.self, from: data).postIdentifier
    }

    // MARK: - Set / Remove

    @Test func testSetProfilePhoto_ReturnsPending() async throws {
        let token = try await registerUser("alice")

        let data = try await stub.setProfilePhoto(sessionManagementToken: token, imageURL: "https://bucket/alice.jpeg")
        let response = try JSONDecoder().decode(ProfilePhotoResponse.self, from: data)

        // The stub approves immediately (no classifier) but still reports the
        // initial pending state, mirroring the backend's eager mode.
        #expect(response.profileImageStatus == "pending")
    }

    @Test func testSetProfilePhoto_AppearsInOwnProfileDetails() async throws {
        let token = try await registerUser("alice")
        _ = try await stub.setProfilePhoto(sessionManagementToken: token, imageURL: "https://bucket/alice.jpeg")

        let data = try await stub.getProfileDetails(sessionManagementToken: token, username: "alice")
        let details = try JSONDecoder().decode(ProfileDetailsResponse.self, from: data)

        // The approved photo is exposed, and the owner sees their own moderation
        // status (which the stub resolved to "approved").
        #expect(details.profileImageUrl == "https://bucket/alice.jpeg")
        #expect(details.profileImageOriginalUrl == "https://bucket/alice.jpeg")
        #expect(details.profileImageStatus == "approved")
    }

    @Test func testProfileImageStatus_AbsentWhenViewingSomeoneElse() async throws {
        let aliceToken = try await registerUser("alice")
        let bobToken = try await registerUser("bob")
        _ = try await stub.setProfilePhoto(sessionManagementToken: aliceToken, imageURL: "https://bucket/alice.jpeg")

        // Bob views Alice's profile: he sees her approved photo, but never the
        // owner-only moderation status.
        let data = try await stub.getProfileDetails(sessionManagementToken: bobToken, username: "alice")
        let details = try JSONDecoder().decode(ProfileDetailsResponse.self, from: data)

        #expect(details.profileImageUrl == "https://bucket/alice.jpeg")
        #expect(details.profileImageStatus == nil, "Owner-only status must be absent for other viewers")
    }

    @Test func testSetProfilePhoto_AppearsInFeedAuthorAvatar() async throws {
        let authorToken = try await registerUser("author")
        let viewerToken = try await registerUser("viewer")
        _ = try await stub.setProfilePhoto(sessionManagementToken: authorToken, imageURL: "https://bucket/author.jpeg")
        _ = try await makePost(authorToken, caption: "a positive post")

        let data = try await stub.getPostsInFeed(sessionManagementToken: viewerToken, batch: 0)
        let posts = try JSONDecoder().decode([Post].self, from: data)

        #expect(posts.count == 1)
        #expect(posts.first?.authorProfileImageUrl == "https://bucket/author.jpeg")
        #expect(posts.first?.authorProfileImageOriginalUrl == "https://bucket/author.jpeg")
    }

    @Test func testSetProfilePhoto_AppearsInCommentAuthorAvatar() async throws {
        let ownerToken = try await registerUser("owner")
        let commenterToken = try await registerUser("commenter")
        _ = try await stub.setProfilePhoto(sessionManagementToken: commenterToken, imageURL: "https://bucket/commenter.jpeg")

        let postId = try await makePost(ownerToken, caption: "hello world")
        let commentData = try await stub.commentOnPost(sessionManagementToken: commenterToken, postIdentifier: postId, commentText: "nice!")
        struct CommentResp: Decodable { let comment_thread_identifier: String }
        let threadId = try JSONDecoder().decode(CommentResp.self, from: commentData).comment_thread_identifier

        let threadData = try await stub.getCommentsForThread(sessionManagementToken: ownerToken, commentThreadIdentifier: threadId, batch: 0)
        struct CommentFields: Decodable {
            let author_username: String
            let author_profile_image_url: String?
            let author_profile_image_original_url: String?
        }
        let comments = try JSONDecoder().decode([CommentFields].self, from: threadData)

        #expect(comments.count == 1)
        #expect(comments.first?.author_profile_image_url == "https://bucket/commenter.jpeg")
        #expect(comments.first?.author_profile_image_original_url == "https://bucket/commenter.jpeg")
    }

    @Test func testRemoveProfilePhoto_ClearsIt() async throws {
        let token = try await registerUser("alice")
        _ = try await stub.setProfilePhoto(sessionManagementToken: token, imageURL: "https://bucket/alice.jpeg")

        let removeData = try await stub.removeProfilePhoto(sessionManagementToken: token)
        let removeResponse = try JSONDecoder().decode(ProfilePhotoResponse.self, from: removeData)
        #expect(removeResponse.profileImageStatus == "none")

        // The profile no longer carries a photo.
        let data = try await stub.getProfileDetails(sessionManagementToken: token, username: "alice")
        let details = try JSONDecoder().decode(ProfileDetailsResponse.self, from: data)
        #expect(details.profileImageUrl == nil)
        #expect(details.profileImageStatus == "none")
    }

    // MARK: - View model set/remove (issue #7)

    @Test func testProfileViewModel_UpdateAndRemovePhoto_ReflectsInHeader() async throws {
        let keychain: KeychainHelperProtocol = MockKeychainHelper()
        let token = try await registerUser("owner")
        let account = "owner_account"
        let session = UserSession(sessionToken: token, username: "owner", userId: "1", isIdentityVerified: false)
        try keychain.save(session, for: GVOAppConstants.keychainService, account: account)

        let user = User(username: "owner", identityIsVerified: false)
        let vm = ProfileViewModel(user: user, api: stub, keychainHelper: keychain, account: account)

        // Under test the real S3 PUT is skipped; the stub records the photo and
        // reloads the profile.
        await vm.updateProfilePhoto(imageData: Data([0xFF, 0xD8, 0xFF]))
        #expect(vm.headerAvatarUrl != nil, "Header avatar should reflect the newly set photo")
        #expect(vm.hasProfilePhoto == true)

        await vm.removeProfilePhoto()
        #expect(vm.headerAvatarUrl == nil, "Header avatar should clear after removal")
        #expect(vm.hasProfilePhoto == false)
    }
}
