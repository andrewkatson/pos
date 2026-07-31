//
//  Positive_Only_SocialTests_Interests.swift
//  Positive Only Social
//
//  Positive interest tags (issues #446/#35): the SettingsViewModel flow against
//  the in-memory stub, plus response DTO decoding.
//

import Testing
import Foundation
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_Interests {

    var stubAPI: StatefulStubbedAPI!
    var keychainHelper: KeychainHelperProtocol!

    init() {
        keychainHelper = MockKeychainHelper()
        stubAPI = StatefulStubbedAPI()
    }

    private func yield(for duration: Duration = .seconds(TestConstants.shortTimeout)) async {
        try? await Task.sleep(for: duration)
    }

    private func setupLoggedInUser(username: String) async throws -> String {
        let data = try await stubAPI.register(username: username, email: "\(username)@test.com", password: "123", rememberMe: "false", ip: "127.0.0.1", dateOfBirth: "1970-01-01")
        struct RegFields: Decodable { let session_management_token: String }
        let token = try JSONDecoder().decode(RegFields.self, from: data).session_management_token
        let userSession = UserSession(sessionToken: token, username: username, userId: "1", isIdentityVerified: false)
        try keychainHelper.save(userSession, for: GVOAppConstants.keychainService, account: "\(username)_account")
        return token
    }

    private func makeViewModel(username: String) -> SettingsViewModel {
        SettingsViewModel(api: stubAPI, keychainHelper: keychainHelper, account: "\(username)_account")
    }

    // MARK: - Load

    @Test func testLoadInterests_prefillsOptionsAndSelection() async throws {
        _ = try await setupLoggedInUser(username: "ada")
        let sut = makeViewModel(username: "ada")
        sut.loadInterests()
        await yield()
        #expect(!sut.interestOptions.isEmpty)
        #expect(sut.interestOptions.contains { $0.slug == "nature" })
        #expect(sut.selectedInterestSlugs.isEmpty)
        #expect(sut.freeformInterests.isEmpty)
    }

    // MARK: - Save

    @Test func testSaveInterests_appliesPicksAndMappedFreeform() async throws {
        _ = try await setupLoggedInUser(username: "grace")
        let sut = makeViewModel(username: "grace")
        sut.toggleInterest("nature")
        sut.addFreeformInterests(["music", "hiking"])
        sut.saveInterests()
        await yield()

        #expect(sut.rejectedInterests.isEmpty)
        #expect(sut.interestsSaved)
        // "hiking" is kept but maps to no bucket; "music" maps to the music bucket.
        #expect(sut.freeformInterests == ["music", "hiking"])

        // The stored selection is the union of picks and mapped freeform.
        let reload = makeViewModel(username: "grace")
        reload.loadInterests()
        await yield()
        #expect(Set(reload.selectedInterestSlugs) == Set(["music", "nature"]))
    }

    @Test func testSaveInterests_rejectsDisallowedFreeform() async throws {
        _ = try await setupLoggedInUser(username: "hopper")
        let sut = makeViewModel(username: "hopper")
        sut.addFreeformInterests(["negative energy"])
        sut.saveInterests()
        await yield()
        #expect(sut.rejectedInterests.count == 1)
        #expect(!sut.interestsSaved)
        #expect(sut.freeformInterests.isEmpty)
    }

    @Test func testSaveInterests_removesDeselected() async throws {
        _ = try await setupLoggedInUser(username: "lovelace")
        let sut = makeViewModel(username: "lovelace")
        sut.toggleInterest("nature")
        sut.toggleInterest("music")
        sut.saveInterests()
        await yield()

        // Deselect nature and re-save: only music remains.
        sut.toggleInterest("nature")
        sut.saveInterests()
        await yield()

        let reload = makeViewModel(username: "lovelace")
        reload.loadInterests()
        await yield()
        #expect(reload.selectedInterestSlugs == ["music"])
    }

    // MARK: - DTO decoding

    @Test func testSetInterestsResponse_decodesLeniently() throws {
        let json = """
        {"categories": ["nature"], "freeform": {"accepted": ["music"], "rejected": [{"text": "bad", "reason": "nope"}]}}
        """.data(using: .utf8)!
        let decoded = try JSONDecoder().decode(SetInterestsResponse.self, from: json)
        #expect(decoded.categories == ["nature"])
        #expect(decoded.freeform.accepted == ["music"])
        #expect(decoded.freeform.rejected.first?.text == "bad")
        #expect(decoded.message == nil)
    }

    @Test func testInterestsResponse_missingFieldsDefaultEmpty() throws {
        let json = "{}".data(using: .utf8)!
        let decoded = try JSONDecoder().decode(InterestsResponse.self, from: json)
        #expect(decoded.categories.isEmpty)
        #expect(decoded.freeform.isEmpty)
    }
}
