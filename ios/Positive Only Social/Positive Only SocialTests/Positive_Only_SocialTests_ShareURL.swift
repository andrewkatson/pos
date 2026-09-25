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

    // MARK: - Profile links (issue #510)

    @Test func profileURLUsesTheProfilePath() {
        let url = ShareURL.profile("sunny_side_up")
        #expect(url?.absoluteString == "https://smiling.social/profile/sunny_side_up")
        #expect(url?.host == "smiling.social")
        #expect(url?.path == "/profile/sunny_side_up")
    }

    @Test func parseReadsBackTheProfileLinkTheBuilderProduces() throws {
        // Round trip, like the post links: the AASA file claims /profile/* too.
        let url = try #require(ShareURL.profile("sunny_side_up"))
        #expect(ShareURL.parse(url) == SharedLink.profile(username: "sunny_side_up"))

        let www = try #require(URL(string: "https://www.smiling.social/profile/sunny_side_up/"))
        #expect(ShareURL.parse(www) == SharedLink.profile(username: "sunny_side_up"))
    }

    @Test func parseAcceptsAUnicodeUsername() throws {
        // The backend's username rule admits Unicode letters, so the parser
        // must too; URLComponents hands the path back decoded.
        let url = try #require(
            URL(string: "https://smiling.social/profile/sonn%C3%A9_%C3%BCber_%E6%97%A5%E6%9C%AC_x"))
        #expect(ShareURL.parse(url) == SharedLink.profile(username: "sonn\u{E9}_\u{FC}ber_\u{65E5}\u{672C}_x"))
    }

    @Test func parseRejectsProfileLinksThatCouldNotBeAUsername() throws {
        // The segment becomes a navigation value, so only a well-formed
        // username (10-150 word characters, the backend's rule) is ever routed.
        let rejected = [
            "https://smiling.social/profile/",
            "https://smiling.social/profile/some%20one",
            "https://smiling.social/profile/a-b",
            "https://smiling.social/profile/ada/posts",
            "https://smiling.social/profile/tooshort9",
            "https://smiling.social/profile/" + String(repeating: "a", count: 151),
        ]
        for string in rejected {
            let url = try #require(URL(string: string))
            #expect(ShareURL.parse(url) == nil, "expected \(string) to be rejected")
        }
    }

    // MARK: - Universal Link parsing (issue #382)

    @Test func parseReadsBackTheLinksTheBuildersProduce() throws {
        // Round trip: whatever we hand the share sheet, iOS can hand back.
        let postURL = try #require(ShareURL.post("abc123"))
        #expect(ShareURL.parse(postURL) == SharedLink.post(SharedPostLink(postIdentifier: "abc123",
                                                                commentIdentifier: nil)))

        let commentURL = try #require(
            ShareURL.comment(postIdentifier: "abc123", commentIdentifier: "def456"))
        #expect(ShareURL.parse(commentURL) == SharedLink.post(SharedPostLink(postIdentifier: "abc123",
                                                                   commentIdentifier: "def456")))
    }

    @Test func parseAcceptsTheWwwHost() throws {
        // Both hosts are claimed in the associated-domains entitlement.
        let url = try #require(URL(string: "https://www.smiling.social/post/abc123"))
        #expect(ShareURL.parse(url)?.postLink?.postIdentifier == "abc123")
    }

    @Test func parseIsCaseInsensitiveAboutTheHost() throws {
        let url = try #require(URL(string: "https://SMILING.social/post/abc123"))
        #expect(ShareURL.parse(url)?.postLink?.postIdentifier == "abc123")
    }

    @Test func parseToleratesATrailingSlash() throws {
        // Chat apps and shorteners add one freely.
        let url = try #require(URL(string: "https://smiling.social/post/abc123/"))
        #expect(ShareURL.parse(url)?.postLink?.postIdentifier == "abc123")
    }

    @Test func parseKeepsThePostWhenTheFragmentIsNotAComment() throws {
        // An unrecognized fragment shouldn't cost the user the post.
        let url = try #require(URL(string: "https://smiling.social/post/abc123#top"))
        #expect(ShareURL.parse(url) == SharedLink.post(SharedPostLink(postIdentifier: "abc123",
                                                            commentIdentifier: nil)))
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
            "https://smiling.social/tags/sunset",               // another route
            "https://smiling.social/",                          // the site root
        ]
        for string in rejected {
            let url = try #require(URL(string: string))
            #expect(ShareURL.parse(url) == nil, "expected \(string) to be rejected")
        }
    }
}
