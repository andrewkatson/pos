//
//  ShareURL.swift
//  Positive Only Social
//

import Foundation

/// Builds website links for the iOS native share sheet (issue #34).
///
/// Scope A only: the shared content is a plain URL to the web app — no
/// deep-linking into the app and no backend changes. These links currently
/// require login on the website, which is expected for Scope A; making them
/// publicly viewable / deep-linking into the app is a tracked follow-up
/// (Scope B) and deliberately not attempted here.
///
/// The builders are pure functions (no I/O, no UIKit) so they're easy to unit
/// test — see `Positive_Only_SocialTests_ShareURL`.
enum ShareURL {

    /// The deployed web app's base URL. The share links point at the website
    /// (CloudFront), mirroring the post/comment routes the web SPA uses.
    static let webBaseURL = "https://smiling.social"

    /// A link to a single post: `https://smiling.social/post/<postIdentifier>`.
    /// Returns `nil` only if the base URL can't be parsed, which never happens
    /// for the constant above but keeps the API honest for callers.
    static func post(_ postIdentifier: String) -> URL? {
        guard var components = URLComponents(string: webBaseURL) else { return nil }
        // Setting `.path` lets URLComponents percent-encode any characters the
        // identifier might contain, rather than string-concatenating a raw path.
        components.path = "/post/\(postIdentifier)"
        return components.url
    }

    /// A link to a specific comment on a post, using a URL fragment the web app
    /// can scroll to:
    /// `https://smiling.social/post/<postIdentifier>#comment-<commentIdentifier>`.
    static func comment(postIdentifier: String, commentIdentifier: String) -> URL? {
        guard var components = URLComponents(string: webBaseURL) else { return nil }
        components.path = "/post/\(postIdentifier)"
        // `.fragment` is percent-encoded by URLComponents when it builds the URL,
        // so an identifier with reserved characters still yields a valid link.
        components.fragment = "comment-\(commentIdentifier)"
        return components.url
    }
}
