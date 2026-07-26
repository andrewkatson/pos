//
//  Positive_Only_SocialTests_ShareURL.swift
//  Positive Only Social
//

import Foundation
import Testing
@testable import Positive_Only_Social

/// Unit tests for the share-link builder used by the iOS native share sheet
/// (issue #34). The builders are pure functions, so these assert the exact
/// website URLs handed to the share sheet.
struct Positive_Only_SocialTests_ShareURL {

    @Test func webBaseURLIsTheWebsite() {
        #expect(ShareURL.webBaseURL == "https://smiling.social")
    }

    @Test func postURLUsesThePostPath() {
        let url = ShareURL.post("abc123")
        #expect(url?.absoluteString == "https://smiling.social/post/abc123")
    }

    @Test func commentURLAppendsTheCommentFragment() {
        let url = ShareURL.comment(postIdentifier: "abc123", commentIdentifier: "def456")
        #expect(url?.absoluteString == "https://smiling.social/post/abc123#comment-def456")
    }

    @Test func commentURLKeepsBasePathAndFragmentComponents() {
        let url = ShareURL.comment(postIdentifier: "abc123", commentIdentifier: "def456")
        #expect(url?.scheme == "https")
        #expect(url?.host == "smiling.social")
        #expect(url?.path == "/post/abc123")
        // URLComponents decodes the fragment back to its raw value.
        #expect(url?.fragment == "comment-def456")
    }

    @Test func postURLBuildsOnTheSharedBase() {
        // The post link is the same base + path the comment link builds on.
        let url = ShareURL.post("xyz")
        #expect(url?.absoluteString.hasPrefix(ShareURL.webBaseURL) == true)
    }
}
