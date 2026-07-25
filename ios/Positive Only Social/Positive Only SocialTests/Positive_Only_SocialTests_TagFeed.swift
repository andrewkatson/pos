//
//  Positive_Only_SocialTests_TagFeed.swift
//  Positive Only Social
//
//  Hashtag support (issue #379): caption parsing and the tag-feed view model.
//

import Testing
import Foundation
@testable import Positive_Only_Social

struct Positive_Only_SocialTests_CaptionSegments {

    @Test func testNoTagsIsASingleTextSegment() {
        #expect(captionSegments("just a caption") == [.text("just a caption")])
    }

    @Test func testEmptyCaptionHasNoSegments() {
        #expect(captionSegments("").isEmpty)
    }

    @Test func testSplitsTextAndTag() {
        #expect(captionSegments("a #sun b") == [
            .text("a "),
            .tag(text: "#sun", name: "sun"),
            .text(" b"),
        ])
    }

    @Test func testTagNameIsLowercasedButTextKeepsCasing() {
        #expect(captionSegments("#SunSet") == [.tag(text: "#SunSet", name: "sunset")])
    }

    @Test func testPunctuationTerminatesATag() {
        #expect(captionSegments("#day!") == [.tag(text: "#day", name: "day"), .text("!")])
    }
}

@MainActor
struct Positive_Only_SocialTests_TagFeedViewModel {

    var stubAPI: StatefulStubbedAPI!
    var keychainHelper: KeychainHelperProtocol!

    init() {
        keychainHelper = MockKeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    private func yield() async {
        try? await Task.sleep(for: .seconds(TestConstants.shortTimeout))
    }

    private func registerUserAndGetToken(username: String) async throws -> String {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        struct RegFields: Decodable { let session_management_token: String }
        return try JSONDecoder().decode(RegFields.self, from: data).session_management_token
    }

    @Test func testFetchNextPage_ReturnsOnlyPostsWithThatTag() async throws {
        let account = "tagFeedReturnsOnlyTagged"
        let sut = TagFeedViewModel(tag: "sunset", api: stubAPI, keychainHelper: keychainHelper, account: account)

        let userAToken = try await registerUserAndGetToken(username: "userA")
        let userBToken = try await registerUserAndGetToken(username: "userB")
        let userSession = UserSession(sessionToken: userAToken, username: "userA", userId: "1", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: account)

        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/1", caption: "a lovely #sunset")
        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/2", caption: "no tag here")

        sut.fetchNextPage()
        await yield()

        #expect(sut.posts.count == 1)
        #expect(sut.posts.first?.imageUrl == "image.url/1")
        #expect(sut.posts.first?.tags.contains("sunset") == true)
    }

    @Test func testFetchNextPage_TagLookupIsCaseInsensitive() async throws {
        let account = "tagFeedCaseInsensitive"
        // Query "sunset" against a caption that wrote "#SunSet".
        let sut = TagFeedViewModel(tag: "sunset", api: stubAPI, keychainHelper: keychainHelper, account: account)

        let userAToken = try await registerUserAndGetToken(username: "userA")
        let userBToken = try await registerUserAndGetToken(username: "userB")
        let userSession = UserSession(sessionToken: userAToken, username: "userA", userId: "1", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: account)

        _ = try await stubAPI.makePost(sessionManagementToken: userBToken, imageURL: "image.url/1", caption: "mixed #SunSet")

        sut.fetchNextPage()
        await yield()

        #expect(sut.posts.count == 1)
    }

    @Test func testFetchNextPage_UnknownTag_ReturnsEmpty() async throws {
        let account = "tagFeedUnknown"
        let sut = TagFeedViewModel(tag: "nothinghere", api: stubAPI, keychainHelper: keychainHelper, account: account)

        let userAToken = try await registerUserAndGetToken(username: "userA")
        let userSession = UserSession(sessionToken: userAToken, username: "userA", userId: "1", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: account)

        sut.fetchNextPage()
        await yield()

        #expect(sut.posts.isEmpty)
        #expect(sut.isLoadingNextPage == false)
    }
}
