//
//  Positive_Only_SocialTests_AuthRequirements.swift
//  Positive Only Social
//

import Testing
@testable import Positive_Only_Social

/// The username length rule must match the backend's `Patterns.username`:
/// 10–150, where 150 is the username column's max_length. A looser client
/// bound lets a 151–500 character name through to a database failure at
/// registration.
struct Positive_Only_SocialTests_AuthRequirements {

    // Module-qualified: AuthRequirements.swift is compiled into the test
    // target too, so an unqualified reference can be ambiguous.
    private func usernameRequirements(_ name: String) -> [Positive_Only_Social.AuthRequirements.Requirement] {
        Positive_Only_Social.AuthRequirements.username(name)
    }

    private func lengthMet(_ name: String) -> Bool {
        usernameRequirements(name)[0].didMeetRequirement
    }

    @Test func usernameLengthRangeMatchesTheBackend() {
        #expect(Positive_Only_Social.AuthRequirements.usernameLengthRange == 10...150)
        #expect(usernameRequirements("")[0].label == "Between 10 and 150 characters")
    }

    @Test func usernameLengthAcceptsTenThroughOneFifty() {
        #expect(!lengthMet(String(repeating: "a", count: 9)))
        #expect(lengthMet(String(repeating: "a", count: 10)))
        #expect(lengthMet(String(repeating: "a", count: 150)))
        #expect(!lengthMet(String(repeating: "a", count: 151)))
        #expect(!lengthMet(String(repeating: "a", count: 500)))
    }

    @Test func usernameLengthCountsScalarsLikeTheBackend() {
        // "e" + combining acute is one grapheme (String.count) but two scalars,
        // and Python's len() counts it as two.
        let decomposed = String(repeating: "e\u{301}", count: 76)
        #expect(decomposed.count == 76)
        #expect(!lengthMet(decomposed))
    }

    @Test func overLongUsernameIsNotAllMet() {
        #expect(!Positive_Only_Social.AuthRequirements.allMet(usernameRequirements(String(repeating: "a", count: 151))))
        #expect(Positive_Only_Social.AuthRequirements.allMet(usernameRequirements(String(repeating: "a", count: 150))))
    }
}
