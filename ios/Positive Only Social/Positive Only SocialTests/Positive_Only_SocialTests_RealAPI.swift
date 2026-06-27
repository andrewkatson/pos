//
//  Positive_Only_SocialTests_RealAPI.swift
//  Positive Only Social
//

import Testing
import Foundation
@testable import Positive_Only_Social

/// Intercepts outbound requests so we can assert the exact URL `RealAPI` builds.
/// Registered globally because `RealAPI` uses `URLSession.shared`, which honors
/// classes registered with `URLProtocol.registerClass` — so interception is
/// scoped to the API host only, leaving any unrelated traffic untouched.
final class CapturingURLProtocol: URLProtocol {
    static let interceptedHost = "api.smiling.social"
    nonisolated(unsafe) static var lastRequestURL: URL?

    override class func canInit(with request: URLRequest) -> Bool {
        guard request.url?.host == interceptedHost else { return false }
        lastRequestURL = request.url
        return true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        let response = HTTPURLResponse(
            url: request.url!, statusCode: 201, httpVersion: nil, headerFields: nil)!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data("{}".utf8))
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

/// Guards the URL construction in `RealAPI`. Posting a comment must hit the
/// singular `comment/` route — the plural `comments/` route is the GET that
/// fetches a batch of threads, so POSTing there 404s (regression for #275).
struct Positive_Only_SocialTests_RealAPI {

    @Test func testCommentOnPostUsesSingularCommentPath() async throws {
        // Reset any value left by a prior run so the assertion can't pass on
        // stale state (e.g. if the request below never fires).
        CapturingURLProtocol.lastRequestURL = nil
        URLProtocol.registerClass(CapturingURLProtocol.self)
        defer { URLProtocol.unregisterClass(CapturingURLProtocol.self) }

        _ = try await RealAPI().commentOnPost(
            sessionManagementToken: "token",
            postIdentifier: "11111111-1111-1111-1111-111111111111",
            commentText: "Nice photo"
        )

        // `URL.path` strips the trailing slash that `RealAPI` appends, so the
        // expected value below is the singular `comment` segment without it.
        #expect(
            CapturingURLProtocol.lastRequestURL?.path
                == "/user_index/posts/11111111-1111-1111-1111-111111111111/comment")
    }
}
