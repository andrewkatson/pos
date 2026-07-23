
import SwiftUI

struct CommentRowView: View {
    let comment: CommentViewData
    let isReported: Bool
    /// Whether this comment was authored by the signed-in user. The backend
    /// rejects liking your own comment, so the like heart is hidden and the
    /// double-tap-to-like gesture is a no-op when true.
    let isOwn: Bool
    /// Whether the thread below this comment is currently collapsed.
    let isCollapsed: Bool
    /// Toggles the collapsed state of the thread below this comment.
    let onToggleCollapse: () -> Void
    /// Actions passed from the parent
    let onLike: () -> Void
    let onUnlike: () -> Void
    let onLongPress: () -> Void
    let onAuthorTap: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            // The comment author's profile photo (issue #7), falling back to the
            // neutral placeholder when they have none.
            ProfileAvatarView(
                imageUrl: comment.authorProfileImageURL,
                originalImageUrl: comment.authorProfileImageOriginalURL,
                size: 36
            )

            VStack(alignment: .leading, spacing: 4) {
                // Username + time header. Tap the author's name to open their
                // profile; tapping the space next to it collapses the thread
                // below this comment (issue #243). A plain tap gesture (not a
                // NavigationLink) so the row's long-press (report/delete) and
                // double-tap (like) gestures aren't swallowed by a nested Button.
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(comment.authorUsername)
                        .fontWeight(.bold)
                        .font(.subheadline)
                        .contentShape(Rectangle())
                        .onTapGesture { onAuthorTap() }
                        // The tap gesture isn't visible to VoiceOver on a
                        // plain Text, so announce this as a button that
                        // opens the author's profile.
                        .accessibilityAddTraits(.isButton)
                        .accessibilityHint("Opens \(comment.authorUsername)'s profile")
                        .accessibilityIdentifier("CommentAuthor")
                    Text(RelativeTime.string(from: comment.createdDate))
                        .font(.caption)
                        .foregroundColor(.secondary)
                    // Three-dots menu next to the timestamp: the discoverable
                    // alternative to long-pressing the comment (issue #304).
                    // Opens the same action menu (Report / Retract Report /
                    // Delete).
                    Button {
                        onLongPress()
                    } label: {
                        Image(systemName: "ellipsis")
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .padding(.vertical, 4)
                            .contentShape(Rectangle())
                    }
                    .accessibilityLabel("Options for comment by \(comment.authorUsername)")
                    .accessibilityIdentifier("CommentOptionsButton")
                    Spacer()
                    Image(systemName: isCollapsed ? "chevron.right" : "chevron.down")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
                .contentShape(Rectangle())
                .onTapGesture { onToggleCollapse() }
                .accessibilityIdentifier("CommentCollapseHeader")

                // The comment body sits below the username/time header line.
                Text(comment.body)
                    .font(.subheadline)
                    .accessibilityIdentifier("CommentText")
                    .accessibilityLabel(comment.body)

                // Info row
                HStack(spacing: 16) {
                    if !isOwn {
                        Button {
                            if comment.isLiked { onUnlike() } else { onLike() }
                        } label: {
                            Image(systemName: comment.isLiked ? "heart.fill" : "heart")
                                .foregroundColor(Color(UIColor.systemRed))
                                .font(.caption)
                        }
                        .accessibilityLabel(comment.isLiked ? "Unlike comment" : "Like comment")
                    }

                    Text("\(comment.likeCount) likes")
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .accessibilityIdentifier("CommentLikesCount")
                    
                    if isReported {
                        Image(systemName: "flag.fill")
                            .foregroundColor(.red)
                            .font(.caption) // Make it a bit smaller
                            .accessibilityIdentifier("ReportedCommentIcon")
                    }
                }
            }
            
            Spacer()
        }
        .padding(.vertical, 8)
        // --- Interactions ---
        .onTapGesture(count: 2) {
            // The backend rejects liking your own comment, so double-tap is
            // a no-op on the current user's own comment.
            guard !isOwn else { return }
            // Drive the action from the server-backed like state
            if comment.isLiked {
                onUnlike()
            } else {
                onLike()
            }
        }
        .onLongPressGesture {
            onLongPress()
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("CommentStack")
        .accessibilityAddTraits(.isButton)
    }
}
