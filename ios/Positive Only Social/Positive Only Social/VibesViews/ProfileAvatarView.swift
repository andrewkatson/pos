//
//  ProfileAvatarView.swift
//  Positive Only Social
//
//  A user's profile photo (issue #7), rendered as a circular avatar next to
//  their name everywhere it appears — feed rows, post detail, comment rows,
//  search results, blocked users, and the profile header.
//

import SwiftUI
import Kingfisher

/// A circular profile avatar. Loads the compressed `imageUrl` and, if that
/// fails, falls back to the full-resolution `originalImageUrl` before giving up
/// to the neutral `person.circle.fill` placeholder. The compressed copy is
/// produced by an async Lambda, so a just-approved photo can 403 in the
/// compressed bucket for a while — the fallback keeps the avatar from showing
/// the placeholder until the user re-logs in. This mirrors `GridPostImage` /
/// `PostDetailImage` for post images (issues #252, #254), and the same
/// compressed→original fallback the website's `Avatar` uses.
///
/// Backed by Kingfisher rather than AsyncImage for the same reasons the post
/// image views are: AsyncImage is one-shot, so a load that fails or gets
/// cancelled (scrolling, navigation transitions) parks the avatar on the
/// placeholder until the view's identity changes; KFImage restarts a failed
/// load when the avatar reappears and disk-caches the result.
struct ProfileAvatarView: View {
    /// Compressed avatar URL, or nil when the user has no approved photo.
    let imageUrl: String?
    /// Full-resolution fallback used if the compressed URL fails to load.
    let originalImageUrl: String?
    /// The diameter of the circular avatar in points.
    var size: CGFloat = 32

    // Once the compressed URL genuinely fails, switch to the original and let
    // Kingfisher load the new URL. Flips at most once, so a failing original
    // lands on the placeholder rather than looping.
    @State private var useOriginal = false

    var body: some View {
        avatarContent
            .frame(width: size, height: size)
            .clipShape(Circle())
            // Decorative: the username is always shown right next to the avatar,
            // so hide it from assistive tech (the website's Avatar uses alt=""
            // for the same reason). But NOT under UI testing — hiding it also
            // removes any parent-applied accessibilityIdentifier (e.g.
            // "ProfileHeaderAvatar") from the tree XCUITest queries.
            .accessibilityHidden(!isUITesting())
            // Reset the fallback when the backing URLs change (a new upload, or
            // the compressed copy becoming available), so a view that fell back
            // to the original retries the fresh compressed URL instead of
            // staying on the original indefinitely — mirroring the website Avatar.
            .onChange(of: imageUrl) { useOriginal = false }
            .onChange(of: originalImageUrl) { useOriginal = false }
    }

    @ViewBuilder
    private var avatarContent: some View {
        if let imageUrl {
            let urlString = useOriginal ? (originalImageUrl ?? imageUrl) : imageUrl
            KFImage(URL(string: urlString))
                // Rides out the just-approved window where the compressed copy
                // isn't in the bucket yet; only HTTP errors are retried, not
                // cancellations.
                .retry(maxCount: 2, interval: .seconds(1))
                .placeholder { placeholder }
                .onFailure { error in
                    // A cancelled load isn't a missing image — the avatar reloads
                    // the same URL when it next appears, so save the fallback for
                    // real failures.
                    guard !error.isTaskCancelled else { return }
                    if !useOriginal, originalImageUrl != nil {
                        useOriginal = true
                    }
                }
                .resizable()
                .scaledToFill()
        } else {
            placeholder
        }
    }

    /// The neutral placeholder shown when the user has no photo (or both URLs
    /// fail). Reuses the `person.circle.fill` symbol the app already used as the
    /// avatar placeholder in comment rows and search rows.
    private var placeholder: some View {
        Image(systemName: "person.circle.fill")
            .resizable()
            .scaledToFit()
            .foregroundColor(.secondary)
    }
}

#Preview {
    VStack(spacing: 16) {
        ProfileAvatarView(imageUrl: nil, originalImageUrl: nil, size: 96)
        ProfileAvatarView(imageUrl: "https://picsum.photos/200", originalImageUrl: nil, size: 48)
        ProfileAvatarView(imageUrl: nil, originalImageUrl: nil, size: 32)
    }
    .padding()
}
