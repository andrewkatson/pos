//
//  Positive_Only_SocialTests_AppealsViewModel.swift
//  Positive Only Social
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_AppealsViewModel {

    let stubAPI: StatefulStubbedAPI
    let keychainHelper: KeychainHelperProtocol

    init() {
        keychainHelper = MockKeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    private func register(_ username: String) async throws -> String {
        let data = try await stubAPI.register(
            username: username, email: "\(username)@test.com", password: "123",
            rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        struct RegFields: Decodable { let session_management_token: String }
        return try JSONDecoder().decode(RegFields.self, from: data).session_management_token
    }

    private func saveSession(token: String, username: String, account: String) throws {
        let session = UserSession(sessionToken: token, username: username, userId: "1", isIdentityVerified: false)
        try keychainHelper.save(session, for: GVOAppConstants.keychainService, account: account)
    }

    /// Author posts, then enough other users report it to hide it. Returns the
    /// author's token and the hidden post id.
    private func makeReportHiddenPost() async throws -> (authorToken: String, postId: String) {
        let authorToken = try await register("author")
        let makeData = try await stubAPI.makePost(
            sessionManagementToken: authorToken, imageURL: "https://example.com/a.jpg", caption: "flagged caption")
        struct PostFields: Decodable { let post_identifier: String }
        let postId = try JSONDecoder().decode(PostFields.self, from: makeData).post_identifier

        for i in 0..<6 {
            let reporterToken = try await register("reporter\(i)")
            _ = try await stubAPI.reportPost(sessionManagementToken: reporterToken, postIdentifier: postId, reason: "bad")
        }
        return (authorToken, postId)
    }

    @Test func testLoadSurfacesHiddenPostsAndAppeals() async throws {
        let (authorToken, postId) = try await makeReportHiddenPost()
        let account = "author_account"
        try saveSession(token: authorToken, username: "author", account: account)

        let vm = AppealsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)
        await vm.load()

        #expect(vm.hiddenPosts.count == 1)
        #expect(vm.hiddenPosts.first?.postIdentifier == postId)
        #expect(vm.hiddenPosts.first?.hiddenReason == "reports")
        #expect(vm.hiddenPosts.first?.hasAppeal == false)
        #expect(vm.appeals.isEmpty)
    }

    @Test func testSubmitAppealRecordsItAndFlipsHasAppeal() async throws {
        let (authorToken, postId) = try await makeReportHiddenPost()
        let account = "author_account"
        try saveSession(token: authorToken, username: "author", account: account)

        let vm = AppealsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)
        await vm.load()

        let ok = await vm.submitAppeal(targetType: "post", targetIdentifier: postId, reason: "please reconsider")

        #expect(ok)
        #expect(vm.appeals.count == 1)
        #expect(vm.appeals.first?.status == "pending")
        #expect(vm.appeals.first?.reason == "please reconsider")
        #expect(vm.hiddenPosts.first?.hasAppeal == true)
    }

    @Test func testCannotAppealVisiblePost() async throws {
        let authorToken = try await register("author")
        let makeData = try await stubAPI.makePost(
            sessionManagementToken: authorToken, imageURL: "https://example.com/a.jpg", caption: "fine")
        struct VisiblePostFields: Decodable { let post_identifier: String }
        let postId = try JSONDecoder().decode(VisiblePostFields.self, from: makeData).post_identifier

        let account = "author_account"
        try saveSession(token: authorToken, username: "author", account: account)
        let vm = AppealsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: account)

        let ok = await vm.submitAppeal(targetType: "post", targetIdentifier: postId, reason: "x")

        #expect(ok == false)
        #expect(vm.errorMessage != nil)
    }
}
