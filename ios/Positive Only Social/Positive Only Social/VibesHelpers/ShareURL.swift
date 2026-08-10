//
//  ShareURL.swift
//  Positive Only Social
//

import Foundation

// Both ends of a shared post link: the URL a post or comment is shared as
// (issue #34), and the app-side parse of the same URL when iOS hands it back as
// a Universal Link (issue #382).
//
// The website renders these links for signed-out recipients too (issue #381),
// so a link is useful whether or not the app is installed — which is exactly
// what makes claiming them with `applinks:smiling.social` safe: a device
// without the app just opens the web page.
//
// Everything here is a pure function (no I/O, no UIKit) so it's easy to unit
// test — see `Positive_Only_SocialTests_ShareURL`.

/// A shared link that resolved to a post, and optionally to one comment on it.
struct SharedPostLink: Equatable {
    let postIdentifier: String
    /// The comment a `#comment-<id>` fragment named, or nil for a plain post
    /// link. Carried so a comment link routes to its post rather than being
    /// rejected outright; the app opens the post detail either way.
    let commentIdentifier: String?
}

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

    /// The website hosts this app claims as Universal Links. Both are listed in
    /// the `associated-domains` entitlement and both serve the same site, so a
    /// link shared with the `www.` prefix opens the app too.
    static let linkHosts: Set<String> = ["smiling.social", "www.smiling.social"]

    /// The inverse of the builders above: what a Universal Link opened by the
    /// system refers to, or nil when the URL is not one of ours (issue #382).
    ///
    /// Deliberately strict. `.onOpenURL` receives whatever the system hands the
    /// app, so the host, scheme and path shape are all checked before the
    /// identifier is used to navigate — a URL that merely looks similar must not
    /// send the user somewhere unexpected. A trailing slash is tolerated because
    /// chat apps and link shorteners add one freely.
    static func parse(_ url: URL) -> SharedPostLink? {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              components.scheme?.lowercased() == "https",
              let host = components.host,
              linkHosts.contains(host.lowercased()) else {
            return nil
        }

        // ["", "post", "<id>"] for /post/<id>, with a trailing "" for a trailing
        // slash. Anything longer is a different route we don't claim.
        var segments = components.path.split(separator: "/", omittingEmptySubsequences: false).map(String.init)
        if segments.last == "" { segments.removeLast() }
        guard segments.count == 3, segments[0] == "", segments[1] == "post" else { return nil }

        let postIdentifier = segments[2]
        guard !postIdentifier.isEmpty else { return nil }

        // URLComponents hands back the decoded fragment, matching what
        // `comment(postIdentifier:commentIdentifier:)` encoded. An unrecognized
        // fragment is ignored rather than failing the whole link: the post is
        // still the right destination.
        var commentIdentifier: String?
        if let fragment = components.fragment, fragment.hasPrefix("comment-") {
            let identifier = String(fragment.dropFirst("comment-".count))
            if !identifier.isEmpty { commentIdentifier = identifier }
        }

        return SharedPostLink(postIdentifier: postIdentifier, commentIdentifier: commentIdentifier)
    }
}
