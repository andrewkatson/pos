//
//  AudienceBadgeView.swift
//  Positive Only Social
//
//  Who can see one of your own posts or comments (issue #518). The tier's
//  badge text and symbol live in PostAudience+Extension.swift.
//

import SwiftUI

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
