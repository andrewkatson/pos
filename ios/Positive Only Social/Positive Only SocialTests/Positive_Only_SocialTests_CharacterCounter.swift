//
//  Positive_Only_SocialTests_CharacterCounter.swift
//  Positive Only Social
//

import Testing
@testable import Positive_Only_Social

struct Positive_Only_SocialTests_CharacterCounter {

    @Test func countsAsciiByCodePoint() {
        #expect(characterCount("hello") == 5)
        #expect(characterCount("") == 0)
    }

    @Test func countsEmojiAsSingleCodePointMatchingBackend() {
        // "💚" is two UTF-16 code units but one unicode scalar (code point),
        // matching Python's len() on the backend.
        #expect(characterCount(String(repeating: "💚", count: 5)) == 5)
    }

    @Test func withinLimitAtAndBelowMax() {
        #expect(isWithinLength(String(repeating: "a", count: 125), max: 125))
        #expect(isWithinLength(String(repeating: "a", count: 124), max: 125))
    }

    @Test func notWithinLimitOverMax() {
        #expect(!isWithinLength(String(repeating: "a", count: 126), max: 125))
    }
}
