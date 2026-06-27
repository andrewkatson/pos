//
//  Positive_Only_SocialTests_RealAPI.swift
//  Positive Only Social
//

import Testing
import Foundation
@testable import Positive_Only_Social

/// Intercepts outbound requests so we can assert the exact URL `RealAPI` builds.
/// Registered globally because `RealAPI` uses `URLSession.shared`, which honors
/// classes registered with `URLProtocol.registerClass`.
final class CapturingURLProtocol: URLProtocol {
    nonisolated(unsafe) static var lastRequestURL: URL?

    override class func canInit(with request: URLRequest) -> Bool {
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
        URLProtocol.registerClass(CapturingURLProtocol.self)
        defer { URLProtocol.unregisterClass(CapturingURLProtocol.self) }

        _ = try await RealAPI().commentOnPost(
            sessionManagementToken: "token",
            postIdentifier: "11111111-1111-1111-1111-111111111111",
            commentText: "Nice photo"
        )

        #expect(
            CapturingURLProtocol.lastRequestURL?.path
                == "/user_index/posts/11111111-1111-1111-1111-111111111111/comment/")
    }
}
