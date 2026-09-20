//
//  AudienceBadgeView.swift
//  Positive Only Social
//
//  Who can see one of your own posts or comments (issue #518).
//

import SwiftUI

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

/// A small badge telling the signed-in user who can see one of their own posts
/// or comments (issue #518). Callers render it only on the viewer's own content:
/// who an author chose to share with is the author's information, the same way
/// "who liked this" is (#478), so a third party never sees it.
///
/// Every tier gets a badge, public included — the point is to answer "who can
/// see this?" at a glance, and a post you meant to keep to family but posted
/// publicly is exactly the case a missing badge would hide.
struct AudienceBadgeView: View {
    /// The raw backend audience; nil (older responses) reads as public.
    let audience: String?
    /// Icon only, for the narrow profile-grid tiles; the description still
    /// reaches VoiceOver.
    var compact: Bool = false

    private var tier: PostAudience { PostAudience.badgeTier(for: audience) }

    var body: some View {
        HStack(spacing: 3) {
            Image(systemName: tier.badgeSymbol)
            if !compact {
                Text(tier.badgeLabel)
            }
        }
        .font(.caption2)
        .foregroundColor(.secondary)
        .padding(.horizontal, compact ? 4 : 6)
        .padding(.vertical, 2)
        .background(Color.secondary.opacity(0.15), in: Capsule())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(tier.badgeDescription)
        .accessibilityIdentifier("AudienceBadge")
    }
}
