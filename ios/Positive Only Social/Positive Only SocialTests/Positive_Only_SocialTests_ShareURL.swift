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

    // MARK: - Universal Link parsing (issue #382)

    @Test func parseReadsBackTheLinksTheBuildersProduce() throws {
        // Round trip: whatever we hand the share sheet, iOS can hand back.
        let postURL = try #require(ShareURL.post("abc123"))
        #expect(ShareURL.parse(postURL) == SharedPostLink(postIdentifier: "abc123",
                                                          commentIdentifier: nil))

        let commentURL = try #require(
            ShareURL.comment(postIdentifier: "abc123", commentIdentifier: "def456"))
        #expect(ShareURL.parse(commentURL) == SharedPostLink(postIdentifier: "abc123",
                                                             commentIdentifier: "def456"))
    }

    @Test func parseAcceptsTheWwwHost() throws {
        // Both hosts are claimed in the associated-domains entitlement.
        let url = try #require(URL(string: "https://www.smiling.social/post/abc123"))
        #expect(ShareURL.parse(url)?.postIdentifier == "abc123")
    }

    @Test func parseIsCaseInsensitiveAboutTheHost() throws {
        let url = try #require(URL(string: "https://SMILING.social/post/abc123"))
        #expect(ShareURL.parse(url)?.postIdentifier == "abc123")
    }

    @Test func parseToleratesATrailingSlash() throws {
        // Chat apps and shorteners add one freely.
        let url = try #require(URL(string: "https://smiling.social/post/abc123/"))
        #expect(ShareURL.parse(url)?.postIdentifier == "abc123")
    }

    @Test func parseKeepsThePostWhenTheFragmentIsNotAComment() throws {
        // An unrecognized fragment shouldn't cost the user the post.
        let url = try #require(URL(string: "https://smiling.social/post/abc123#top"))
        #expect(ShareURL.parse(url) == SharedPostLink(postIdentifier: "abc123",
                                                      commentIdentifier: nil))
    }

    @Test func parseRejectsURLsThatAreNotOurs() throws {
        // .onOpenURL receives whatever the system hands the app, so a URL that
        // merely looks similar must not navigate anywhere.
        let rejected = [
            "https://smiling.social.evil.example/post/abc123",  // suffix, not our host
            "https://evil.example/post/abc123",                 // wrong host entirely
            "http://smiling.social/post/abc123",                // not https
            "https://smiling.social/posts/abc123",              // different route
            "https://smiling.social/post/",                     // no identifier
            "https://smiling.social/post/abc123/extra",         // deeper path
            "https://smiling.social/profile/ada",               // another route
            "https://smiling.social/",                          // the site root
        ]
        for string in rejected {
            let url = try #require(URL(string: string))
            #expect(ShareURL.parse(url) == nil, "expected \(string) to be rejected")
        }
    }
}
