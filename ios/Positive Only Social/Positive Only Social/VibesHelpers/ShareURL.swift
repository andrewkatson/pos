//
//  ShareURL.swift
//  Positive Only Social
//

import Foundation

// Both ends of a shared link: the URL a post, comment (issue #34) or profile
// (issue #510) is shared as, and the app-side parse of the same URL when iOS
// hands it back as a Universal Link (issue #382).
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

/// What a Universal Link the system opened us with refers to. The two routes go
/// to different screens, so the parse says which.
enum SharedLink: Equatable {
    case post(SharedPostLink)
    case profile(username: String)

    /// The post link, when this is one — a convenience for the common case.
    var postLink: SharedPostLink? {
        if case .post(let link) = self { return link }
        return nil
    }
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

    /// A link to a user's profile (issue #510):
    /// `https://smiling.social/profile/<username>`. Shared from the profile's
    /// options menu, your own or anyone else's. The website renders it for a
    /// recipient with no account through the public profile endpoints, and the
    /// AASA file claims `/profile/*` too, so with the app installed it opens
    /// that user's profile screen.
    static func profile(_ username: String) -> URL? {
        guard var components = URLComponents(string: webBaseURL) else { return nil }
        components.path = "/profile/\(username)"
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

    /// Usernames are 10–500 word characters (letters, digits, underscore) — the
    /// backend's `Patterns.alphanumeric`, which registration and the profile
    /// endpoints all enforce — so a profile segment that isn't is not a profile
    /// we have a screen for. A predicate rather than a regex so Unicode letters
    /// count, as they do server-side; the length is counted in scalars for the
    /// same reason (the backend counts code points, not grapheme clusters).
    private static func isPlausibleUsername(_ value: String) -> Bool {
        (10...500).contains(value.unicodeScalars.count)
            && value.allSatisfy { $0.isLetter || $0.isNumber || $0 == "_" }
    }

    /// The inverse of the builders above: what a Universal Link opened by the
    /// system refers to, or nil when the URL is not one of ours (issue #382).
    ///
    /// Deliberately strict. `.onOpenURL` receives whatever the system hands the
    /// app, so the host, scheme and path shape are all checked before the
    /// identifier is used to navigate — a URL that merely looks similar must not
    /// send the user somewhere unexpected. A trailing slash is tolerated because
    /// chat apps and link shorteners add one freely.
    static func parse(_ url: URL) -> SharedLink? {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              components.scheme?.lowercased() == "https",
              let host = components.host,
              linkHosts.contains(host.lowercased()) else {
            return nil
        }

        // ["", "post", "<id>"] for /post/<id> (or ["", "profile", "<name>"]),
        // with a trailing "" for a trailing slash. Anything longer is a
        // different route we don't claim.
        var segments = components.path.split(separator: "/", omittingEmptySubsequences: false).map(String.init)
        if segments.last == "" { segments.removeLast() }
        guard segments.count == 3, segments[0] == "" else { return nil }

        let identifier = segments[2]
        guard !identifier.isEmpty else { return nil }

        switch segments[1] {
        case "post":
            // URLComponents hands back the decoded fragment, matching what
            // `comment(postIdentifier:commentIdentifier:)` encoded. An
            // unrecognized fragment is ignored rather than failing the whole
            // link: the post is still the right destination.
            var commentIdentifier: String?
            if let fragment = components.fragment, fragment.hasPrefix("comment-") {
                let commentPart = String(fragment.dropFirst("comment-".count))
                if !commentPart.isEmpty { commentIdentifier = commentPart }
            }
            return .post(SharedPostLink(postIdentifier: identifier, commentIdentifier: commentIdentifier))
        case "profile":
            // `components.path` is already percent-decoded, so an encoded space
            // or slash fails the pattern here rather than reaching navigation.
            guard isPlausibleUsername(identifier) else { return nil }
            return .profile(username: identifier)
        default:
            return nil
        }
    }
}
