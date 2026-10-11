//
//  Positive_Only_SocialTests_PrivateAccounts.swift
//  Positive Only Social
//
//  Private accounts and follow requests (issue #96): the stub's privacy rule,
//  the profile's Follow / Requested / Following states, the follow requests
//  list, and the Settings toggle.
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_PrivateAccounts {

    let stubAPI: StatefulStubbedAPI
    let keychainHelper: KeychainHelperProtocol

    init() {
        keychainHelper = MockKeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    // MARK: - Helpers

    private func yield(for duration: Duration = .seconds(TestConstants.shortTimeout)) async {
        try? await Task.sleep(for: duration)
    }

    private func registerUser(username: String) async throws -> (token: String, user: User) {
        let data = try await stubAPI.register(
            username: username, email: "\(username)@test.com", password: "123",
            rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        struct RegFields: Decodable { let session_management_token: String }
        let token = try JSONDecoder().decode(RegFields.self, from: data).session_management_token
        return (token, User(username: username, identityIsVerified: false))
    }

    private func signIn(_ user: User, token: String) throws -> String {
        let account = "\(user.username)_account"
        let session = UserSession(sessionToken: token, username: user.username, userId: "1", isIdentityVerified: false)
        try keychainHelper.save(session, for: GVOAppConstants.keychainService, account: account)
        return account
    }

    private func profile(_ token: String, of username: String) async throws -> ProfileDetailsResponse {
        let data = try await stubAPI.getProfileDetails(sessionManagementToken: token, username: username)
        return try JSONDecoder().decode(ProfileDetailsResponse.self, from: data)
    }

    /// A private author with one post, plus a viewer who does not follow them.
    private func privateAuthorAndViewer() async throws
        -> (authorToken: String, author: User, viewerToken: String, viewer: User) {
        let (authorToken, author) = try await registerUser(username: "privateAuthor")
        _ = try await stubAPI.setAccountPrivacy(sessionManagementToken: authorToken, isPrivate: true)
        _ = try await stubAPI.makePost(sessionManagementToken: authorToken, imageURL: "img/1", caption: "Hello")
        let (viewerToken, viewer) = try await registerUser(username: "curiousViewer")
        return (authorToken, author, viewerToken, viewer)
    }

    // MARK: - Stub API

    @Test func followingPrivateAccountFilesRequestAndHidesPosts() async throws {
        let (authorToken, _, viewerToken, _) = try await privateAuthorAndViewer()

        let data = try await stubAPI.followUser(
            sessionManagementToken: viewerToken, username: "privateAuthor",
            category: FollowCategory.friend.rawValue)
        #expect(try JSONDecoder().decode(FollowResponse.self, from: data).followRequestPending == true)

        let locked = try await profile(viewerToken, of: "privateAuthor")
        #expect(locked.isPrivate == true)
        #expect(locked.isFollowing == false)
        #expect(locked.followRequestPending == true)
        #expect(locked.postCount == 0)
        let lockedGrid = try await stubAPI.getPostsForUser(
            sessionManagementToken: viewerToken, username: "privateAuthor", batch: 0)
        #expect(try JSONDecoder().decode([Post].self, from: lockedGrid).isEmpty)

        let requestsData = try await stubAPI.getFollowRequests(sessionManagementToken: authorToken)
        #expect(try JSONDecoder().decode([User].self, from: requestsData).map(\.username) == ["curiousViewer"])
        #expect(try await profile(authorToken, of: "privateAuthor").followRequestCount == 1)

        _ = try await stubAPI.approveFollowRequest(sessionManagementToken: authorToken, username: "curiousViewer")

        let unlocked = try await profile(viewerToken, of: "privateAuthor")
        #expect(unlocked.isFollowing == true)
        #expect(unlocked.followCategory == FollowCategory.friend.rawValue)
        #expect(unlocked.postCount == 1)
    }

    @Test func nonFollowerCannotFindOrInteractWithPrivatePost() async throws {
        let (authorToken, _) = try await registerUser(username: "beachAuthor")
        _ = try await stubAPI.setAccountPrivacy(sessionManagementToken: authorToken, isPrivate: true)
        let postData = try await stubAPI.makePost(
            sessionManagementToken: authorToken, imageURL: "img/1", caption: "sunny #beach")
        let postId = try JSONDecoder().decode(MakePostResponse.self, from: postData).postIdentifier
        struct CommentIds: Decodable { let comment_thread_identifier, comment_identifier: String }
        let commentData = try await stubAPI.commentOnPost(
            sessionManagementToken: authorToken, postIdentifier: postId, commentText: "lovely")
        let ids = try JSONDecoder().decode(CommentIds.self, from: commentData)
        let (viewerToken, _) = try await registerUser(username: "beachViewer")

        let tagData = try await stubAPI.getPostsForTag(sessionManagementToken: viewerToken, tag: "beach", batch: 0)
        #expect(try JSONDecoder().decode([Post].self, from: tagData).isEmpty)
        await #expect(throws: (any Error).self) {
            _ = try await stubAPI.likePost(sessionManagementToken: viewerToken, postIdentifier: postId)
        }
        await #expect(throws: (any Error).self) {
            _ = try await stubAPI.reportPost(sessionManagementToken: viewerToken, postIdentifier: postId, reason: "x")
        }
        await #expect(throws: (any Error).self) {
            _ = try await stubAPI.commentOnPost(sessionManagementToken: viewerToken, postIdentifier: postId, commentText: "hi")
        }
        await #expect(throws: (any Error).self) {
            _ = try await stubAPI.likeComment(
                sessionManagementToken: viewerToken, postIdentifier: postId,
                commentThreadIdentifier: ids.comment_thread_identifier, commentIdentifier: ids.comment_identifier)
        }
        await #expect(throws: (any Error).self) {
            _ = try await stubAPI.reportComment(
                sessionManagementToken: viewerToken, postIdentifier: postId,
                commentThreadIdentifier: ids.comment_thread_identifier, commentIdentifier: ids.comment_identifier,
                reason: "x")
        }

        await #expect(throws: (any Error).self) {
            _ = try await stubAPI.getCommentsForPost(
                sessionManagementToken: viewerToken, postIdentifier: postId, batch: 0, category: nil)
        }
        await #expect(throws: (any Error).self) {
            _ = try await stubAPI.getCommentsForThread(
                sessionManagementToken: viewerToken, commentThreadIdentifier: ids.comment_thread_identifier,
                batch: 0, category: nil)
        }
        await #expect(throws: (any Error).self) {
            _ = try await stubAPI.replyToCommentThread(
                sessionManagementToken: viewerToken, postIdentifier: postId,
                commentThreadIdentifier: ids.comment_thread_identifier, commentText: "hi",
                formatting: nil, audience: nil)
        }

        await #expect(throws: (any Error).self) {
            _ = try await stubAPI.savePost(sessionManagementToken: viewerToken, postIdentifier: postId)
        }
        // Pairing the private comment's ids with an unrelated public post's id
        // must not get past the privacy check either.
        let (otherToken, _) = try await registerUser(username: "publicNeighbor")
        let publicData = try await stubAPI.makePost(sessionManagementToken: otherToken, imageURL: "img/2", caption: "hi")
        let publicPostId = try JSONDecoder().decode(MakePostResponse.self, from: publicData).postIdentifier
        await #expect(throws: (any Error).self) {
            _ = try await stubAPI.likeComment(
                sessionManagementToken: viewerToken, postIdentifier: publicPostId,
                commentThreadIdentifier: ids.comment_thread_identifier, commentIdentifier: ids.comment_identifier)
        }

        _ = try await stubAPI.followUser(sessionManagementToken: viewerToken, username: "beachAuthor")
        _ = try await stubAPI.approveFollowRequest(sessionManagementToken: authorToken, username: "beachViewer")
        let unlockedTag = try await stubAPI.getPostsForTag(sessionManagementToken: viewerToken, tag: "beach", batch: 0)
        #expect(try JSONDecoder().decode([Post].self, from: unlockedTag).count == 1)
        _ = try await stubAPI.likePost(sessionManagementToken: viewerToken, postIdentifier: postId)
    }

    @Test func requestRefusedWhenRequesterBlockedThePrivateAccount() async throws {
        let (_, _, viewerToken, _) = try await privateAuthorAndViewer()
        _ = try await stubAPI.toggleBlock(sessionManagementToken: viewerToken, username: "privateAuthor")

        await #expect(throws: (any Error).self) {
            _ = try await stubAPI.followUser(sessionManagementToken: viewerToken, username: "privateAuthor")
        }
    }

    @Test func deletingARequesterDropsTheirRequest() async throws {
        let (authorToken, _, viewerToken, _) = try await privateAuthorAndViewer()
        _ = try await stubAPI.followUser(sessionManagementToken: viewerToken, username: "privateAuthor")

        _ = try await stubAPI.deleteUser(sessionManagementToken: viewerToken)

        let requests = try await stubAPI.getFollowRequests(sessionManagementToken: authorToken)
        #expect(try JSONDecoder().decode([User].self, from: requests).isEmpty)
        #expect(try await profile(authorToken, of: "privateAuthor").followRequestCount == 0)
    }

    @Test func goingPublicApprovesPendingRequests() async throws {
        let (authorToken, _, viewerToken, _) = try await privateAuthorAndViewer()
        _ = try await stubAPI.followUser(sessionManagementToken: viewerToken, username: "privateAuthor")

        _ = try await stubAPI.setAccountPrivacy(sessionManagementToken: authorToken, isPrivate: false)

        #expect(try await profile(viewerToken, of: "privateAuthor").isFollowing == true)
        let me = try await stubAPI.getCurrentUser(sessionManagementToken: authorToken)
        #expect(try JSONDecoder().decode(CurrentUserFields.self, from: me).isPrivate == false)
    }

    // MARK: - ProfileViewModel

    @Test func profileFollowOnPrivateAccountShowsRequested() async throws {
        let (_, author, viewerToken, viewer) = try await privateAuthorAndViewer()
        let account = try signIn(viewer, token: viewerToken)
        let sut = ProfileViewModel(user: author, api: stubAPI, keychainHelper: keychainHelper, account: account)
        sut.fetchProfileDetails()
        await yield()
        #expect(sut.isLocked == true, "Pre-condition: a private account you don't follow is locked")

        sut.toggleFollow()
        await yield()

        #expect(sut.followRequestPending == true)
        #expect(sut.isFollowing == false)
        #expect(sut.isLocked == true, "A request is not a follow")
        #expect(sut.profileDetails?.followerCount == 0, "Counts don't move for a request")
    }

    @Test func profileTappingRequestedCancelsTheRequest() async throws {
        let (authorToken, author, viewerToken, viewer) = try await privateAuthorAndViewer()
        _ = try await stubAPI.followUser(sessionManagementToken: viewerToken, username: "privateAuthor")
        let account = try signIn(viewer, token: viewerToken)
        let sut = ProfileViewModel(user: author, api: stubAPI, keychainHelper: keychainHelper, account: account)
        sut.fetchProfileDetails()
        await yield()
        #expect(sut.followRequestPending == true, "Pre-condition: request pending")

        sut.toggleFollow()
        await yield()

        #expect(sut.followRequestPending == false)
        let remaining = try await stubAPI.getFollowRequests(sessionManagementToken: authorToken)
        #expect(try JSONDecoder().decode([User].self, from: remaining).isEmpty)
    }

    @Test func profileApprovedFollowerIsNotLocked() async throws {
        let (authorToken, author, viewerToken, viewer) = try await privateAuthorAndViewer()
        _ = try await stubAPI.followUser(sessionManagementToken: viewerToken, username: "privateAuthor")
        _ = try await stubAPI.approveFollowRequest(sessionManagementToken: authorToken, username: "curiousViewer")
        let account = try signIn(viewer, token: viewerToken)
        let sut = ProfileViewModel(user: author, api: stubAPI, keychainHelper: keychainHelper, account: account)

        sut.fetchProfileDetails()
        sut.fetchUserPosts()
        await yield()

        #expect(sut.isLocked == false)
        #expect(sut.userPosts.count == 1)
    }

    @Test func ownPrivateProfileIsNeverLocked() async throws {
        let (authorToken, author, viewerToken, _) = try await privateAuthorAndViewer()
        _ = try await stubAPI.followUser(sessionManagementToken: viewerToken, username: "privateAuthor")
        let account = try signIn(author, token: authorToken)
        let sut = ProfileViewModel(user: author, api: stubAPI, keychainHelper: keychainHelper, account: account)

        sut.fetchProfileDetails()
        await yield()

        #expect(sut.isLocked == false)
        #expect(sut.followRequestCount == 1)
    }

    @Test func profileFollowAfterOwnerWentPrivateReloadsTheProfile() async throws {
        // The profile loads while the account is public, then the owner goes
        // private: the follow files a request, so the cached grid must go.
        let (authorToken, author) = try await registerUser(username: "turncoat")
        _ = try await stubAPI.makePost(sessionManagementToken: authorToken, imageURL: "img/1", caption: "Hi")
        let (viewerToken, viewer) = try await registerUser(username: "lateFollower")
        let account = try signIn(viewer, token: viewerToken)
        let sut = ProfileViewModel(user: author, api: stubAPI, keychainHelper: keychainHelper, account: account)
        sut.fetchProfileDetails()
        sut.fetchUserPosts()
        await yield()
        #expect(sut.userPosts.count == 1, "Pre-condition: public grid loaded")

        _ = try await stubAPI.setAccountPrivacy(sessionManagementToken: authorToken, isPrivate: true)
        sut.toggleFollow()
        await yield()

        #expect(sut.followRequestPending == true)
        #expect(sut.isFollowing == false)
        #expect(sut.isLocked == true)
        #expect(sut.userPosts.isEmpty, "The stale public grid is replaced")
    }

    @Test func answeringRequestsRefreshesTheOwnersProfile() async throws {
        let (authorToken, author, viewerToken, _) = try await privateAuthorAndViewer()
        _ = try await stubAPI.followUser(sessionManagementToken: viewerToken, username: "privateAuthor")
        let account = try signIn(author, token: authorToken)
        let center = NotificationCenter()
        let profile = ProfileViewModel(user: author, api: stubAPI, keychainHelper: keychainHelper,
                                       account: account, notificationCenter: center)
        profile.fetchProfileDetails()
        await yield()
        #expect(profile.followRequestCount == 1, "Pre-condition: one request waiting")

        let requests = FollowRequestsViewModel(api: stubAPI, keychainHelper: keychainHelper,
                                               account: account, notificationCenter: center)
        await requests.approve(username: "curiousViewer")
        await yield()

        #expect(profile.followRequestCount == 0)
        #expect(profile.profileDetails?.followerCount == 1)
    }

    @Test func cancelAfterTheOwnerApprovedReloadsAsFollower() async throws {
        let (authorToken, author, viewerToken, viewer) = try await privateAuthorAndViewer()
        _ = try await stubAPI.followUser(sessionManagementToken: viewerToken, username: "privateAuthor")
        let account = try signIn(viewer, token: viewerToken)
        let sut = ProfileViewModel(user: author, api: stubAPI, keychainHelper: keychainHelper, account: account)
        sut.fetchProfileDetails()
        await yield()
        #expect(sut.followRequestPending == true, "Pre-condition: Requested")

        // The owner approves while this profile is open; tapping Requested then
        // finds nothing to cancel.
        _ = try await stubAPI.approveFollowRequest(sessionManagementToken: authorToken, username: "curiousViewer")
        sut.toggleFollow()
        await yield()

        #expect(sut.followRequestPending == false)
        #expect(sut.isFollowing == true)
        #expect(sut.isLocked == false)
        #expect(sut.userPosts.count == 1)
    }

    @Test func privacyChangeRefreshesTheOwnersProfile() async throws {
        let (token, user) = try await registerUser(username: "togglingOwner")
        let account = try signIn(user, token: token)
        let center = NotificationCenter()
        let profile = ProfileViewModel(user: user, api: stubAPI, keychainHelper: keychainHelper,
                                       account: account, notificationCenter: center)
        profile.fetchProfileDetails()
        let settings = SettingsViewModel(api: stubAPI, keychainHelper: keychainHelper,
                                         account: account, notificationCenter: center)
        settings.loadCurrentUser()
        await yield()
        #expect(profile.profileDetails?.isPrivate == false, "Pre-condition: public")

        settings.setAccountPrivacy(true)
        await yield()

        #expect(profile.profileDetails?.isPrivate == true)
    }

    // MARK: - FollowRequestsViewModel

    @Test func followRequestsApproveAndDenyDropRows() async throws {
        let (authorToken, author, viewerToken, _) = try await privateAuthorAndViewer()
        let (otherToken, _) = try await registerUser(username: "otherFan")
        _ = try await stubAPI.followUser(sessionManagementToken: viewerToken, username: "privateAuthor")
        _ = try await stubAPI.followUser(sessionManagementToken: otherToken, username: "privateAuthor")
        let account = try signIn(author, token: authorToken)
        let sut = FollowRequestsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)

        await sut.load()
        #expect(sut.requests.map(\.username) == ["otherFan", "curiousViewer"], "Newest first")
        #expect(sut.hasLoaded == true)

        await sut.approve(username: "curiousViewer")
        await sut.deny(username: "otherFan")

        #expect(sut.requests.isEmpty)
        #expect(sut.errorMessage == nil)
        #expect(try await profile(viewerToken, of: "privateAuthor").isFollowing == true)
        #expect(try await profile(otherToken, of: "privateAuthor").isFollowing == false)
    }

    @Test func followRequestsFailedLoadIsNotReportedAsLoaded() async throws {
        // No session in the keychain under this account: the load can't run.
        let sut = FollowRequestsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "nobody_account")

        await sut.load()

        #expect(sut.hasLoaded == false)
        #expect(sut.requests.isEmpty)
    }

    @Test func followRequestsUnknownRequestSetsError() async throws {
        let (authorToken, author, viewerToken, _) = try await privateAuthorAndViewer()
        _ = try await stubAPI.followUser(sessionManagementToken: viewerToken, username: "privateAuthor")
        let account = try signIn(author, token: authorToken)
        let sut = FollowRequestsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)
        await sut.load()

        await sut.approve(username: "nobodyAtAll")

        #expect(sut.errorMessage != nil)
        #expect(sut.requests.map(\.username) == ["curiousViewer"])
    }

    // MARK: - SettingsViewModel

    @Test func settingsPrivacyToggleLoadsAndSaves() async throws {
        let (token, user) = try await registerUser(username: "settingsUser")
        let account = try signIn(user, token: token)
        let sut = SettingsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)

        sut.loadCurrentUser()
        await yield()
        #expect(sut.isPrivate == false)

        sut.setAccountPrivacy(true)
        #expect(sut.isPrivate == true, "Optimistic flip")
        await yield()

        #expect(sut.isSavingPrivacy == false)
        #expect(sut.showingErrorAlert == false)
        let me = try await stubAPI.getCurrentUser(sessionManagementToken: token)
        #expect(try JSONDecoder().decode(CurrentUserFields.self, from: me).isPrivate == true)
    }

    @Test func settingsPrivacyToggleIgnoredBeforeLoad() async throws {
        let (token, user) = try await registerUser(username: "earlyUser")
        let account = try signIn(user, token: token)
        let sut = SettingsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)

        sut.setAccountPrivacy(true)
        await yield()

        #expect(sut.isPrivate == nil)
        let me = try await stubAPI.getCurrentUser(sessionManagementToken: token)
        #expect(try JSONDecoder().decode(CurrentUserFields.self, from: me).isPrivate == false)
    }
}
