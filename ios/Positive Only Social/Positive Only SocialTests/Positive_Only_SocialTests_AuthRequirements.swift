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

    @Test func combiningMarksAreNotWordCharactersLikeTheBackend() {
        // 75 "e" + U+0301 pairs are 150 scalars, inside the length range, but
        // Python's \w rejects the combining mark, so registration would fail.
        // Foundation's ICU \w admits it; the rule must not.
        let decomposed = String(repeating: "e\u{301}", count: 75)
        #expect(lengthMet(decomposed))
        #expect(!Positive_Only_Social.AuthRequirements.allMet(usernameRequirements(decomposed)))
        // Connector punctuation other than "_" is also ICU-\w-only.
        #expect(!Positive_Only_Social.AuthRequirements.allMet(usernameRequirements("sunny\u{203F}side_up")))
    }

    @Test func unicodeLettersAndNumbersAreWordCharactersLikeTheBackend() {
        // All of these match Python's \w: a precomposed accented letter, a
        // supplementary-plane letter, a letter number (Ⅻ) and an other number (①).
        #expect(Positive_Only_Social.AuthRequirements.allMet(usernameRequirements("sonn\u{E9}_\u{216B}_\u{2460}_ok")))
        #expect(Positive_Only_Social.AuthRequirements.allMet(
            usernameRequirements(String(repeating: "\u{1D400}", count: 150))))
    }

    @Test func nonWordCharactersAreRejected() {
        #expect(!Positive_Only_Social.AuthRequirements.allMet(usernameRequirements("has a space here")))
        #expect(!Positive_Only_Social.AuthRequirements.allMet(usernameRequirements("dash-in-the-name")))
    }

    @Test func overLongUsernameIsNotAllMet() {
        #expect(!Positive_Only_Social.AuthRequirements.allMet(usernameRequirements(String(repeating: "a", count: 151))))
        #expect(Positive_Only_Social.AuthRequirements.allMet(usernameRequirements(String(repeating: "a", count: 150))))
    }
}
