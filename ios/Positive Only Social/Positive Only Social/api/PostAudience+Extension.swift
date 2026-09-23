//
//  PostAudience+Extension.swift
//  Positive Only Social
//
//  Badge text and symbol for each audience tier (issue #518), consumed by
//  AudienceBadgeView.
//

import Foundation

extension PostAudience {
    /// The tier a post's or comment's raw `audience` value names. A nil or
    /// unrecognised value is public — the backend's default for older rows and
    /// how it treats an omitted audience — so the badge never comes up empty.
    static func badgeTier(for rawValue: String?) -> PostAudience {
        rawValue.flatMap { PostAudience(rawValue: $0) } ?? .public
    }

    /// Short visible label for the badge. `displayName` reads "People I follow"
    /// for the picker; the badge wants one word next to the like count.
    var badgeLabel: String {
        switch self {
        case .public: return "Public"
        case .following: return "Following"
        case .friends: return "Friends"
        case .family: return "Family"
        }
    }

    /// SF Symbol for the badge, widening as the circle does: one globe, then
    /// two people, three people, and home.
    var badgeSymbol: String {
        switch self {
        case .public: return "globe"
        case .following: return "person.2"
        case .friends: return "person.3"
        case .family: return "house"
        }
    }

    /// What the badge announces, spelling out who is admitted.
    var badgeDescription: String {
        switch self {
        case .public: return "Visible to anyone"
        case .following: return "Visible to people you follow"
        case .friends: return "Visible to friends and family"
        case .family: return "Visible to family only"
        }
    }
}
