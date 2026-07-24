
import SwiftUI
import UIKit

/// Presentation helpers mapping the curated formatting keys (issue #318) to
/// concrete SwiftUI fonts/colors, and building an `AttributedString` for a
/// comment's inline spans. Kept here (not in the Foundation-only Models layer)
/// so the model stays UI-free; declared top-level so every view can use it.
enum TextFormatting {
    /// The whole-caption font for a caption-font key at a given point size.
    static func captionFont(_ key: String, size: CGFloat) -> Font {
        switch key {
        case "serif": return .system(size: size, design: .serif)
        case "monospace": return .system(size: size, design: .monospaced)
        case "rounded": return .system(size: size, design: .rounded)
        case "handwriting": return .custom("Snell Roundhand", size: size)
        default: return .system(size: size)
        }
    }

    /// The tile background color for a background-color key, or nil for default.
    static func backgroundColor(_ key: String) -> Color? {
        switch key {
        case "sky": return Color(red: 0.874, green: 0.945, blue: 1.0)
        case "mint": return Color(red: 0.863, green: 0.969, blue: 0.910)
        case "blush": return Color(red: 1.0, green: 0.894, blue: 0.925)
        case "lemon": return Color(red: 1.0, green: 0.965, blue: 0.800)
        case "lavender": return Color(red: 0.925, green: 0.890, blue: 1.0)
        default: return nil
        }
    }

    /// A legible foreground color for text on the given background, or nil.
    static func foregroundColor(_ key: String) -> Color? {
        switch key {
        case "sky": return Color(red: 0.063, green: 0.200, blue: 0.290)
        case "mint": return Color(red: 0.078, green: 0.263, blue: 0.169)
        case "blush": return Color(red: 0.290, green: 0.075, blue: 0.153)
        case "lemon": return Color(red: 0.290, green: 0.239, blue: 0.039)
        case "lavender": return Color(red: 0.184, green: 0.102, blue: 0.290)
        default: return nil
        }
    }

    /// Multiplier applied to the base point size for a comment text-size key.
    static func sizeScale(_ key: String) -> CGFloat {
        switch key {
        case "small": return 0.85
        case "large": return 1.25
        case "xlarge": return 1.5
        default: return 1.0
        }
    }

    /// Builds an `AttributedString` applying inline bold/italic/size spans over
    /// `text`. Offsets are UTF-16 code units. Spans arrive sorted and
    /// non-overlapping (backend-enforced); offsets are clamped so a malformed
    /// payload degrades to plain text rather than crashing.
    static func attributedComment(_ text: String, spans: [CommentFormatSpan]?, baseSize: CGFloat) -> AttributedString {
        func plainPiece(_ substring: String) -> AttributedString {
            var piece = AttributedString(substring)
            piece.font = .system(size: baseSize)
            return piece
        }
        guard let spans, !spans.isEmpty else { return plainPiece(text) }

        let utf16Count = text.utf16.count
        var result = AttributedString("")
        var cursor = 0
        for span in spans {
            let start = max(cursor, min(span.start, utf16Count))
            let end = max(start, min(span.end, utf16Count))
            if start > cursor {
                // If a boundary falls inside a surrogate pair the slice fails;
                // fall back to plain text for the whole comment rather than
                // dropping any of it.
                guard let gap = Self.substring(of: text, startUTF16: cursor, endUTF16: start) else {
                    return plainPiece(text)
                }
                result.append(plainPiece(gap))
            }
            if start < end {
                guard let styled = Self.substring(of: text, startUTF16: start, endUTF16: end) else {
                    return plainPiece(text)
                }
                var piece = AttributedString(styled)
                var font = Font.system(size: baseSize * sizeScale(span.size))
                if span.bold { font = font.bold() }
                if span.italic { font = font.italic() }
                piece.font = font
                result.append(piece)
            }
            cursor = end
        }
        if cursor < utf16Count {
            guard let tail = Self.substring(of: text, startUTF16: cursor, endUTF16: utf16Count) else {
                return plainPiece(text)
            }
            result.append(plainPiece(tail))
        }
        return result
    }

    /// The base point size for comment bodies, honoring Dynamic Type.
    static var commentBaseSize: CGFloat {
        UIFont.preferredFont(forTextStyle: .subheadline).pointSize
    }

    /// Slices `text` by UTF-16 offsets, returning nil if an offset falls inside
    /// a surrogate pair (a malformed span) so the caller can skip it.
    private static func substring(of text: String, startUTF16: Int, endUTF16: Int) -> String? {
        let u = text.utf16
        guard let s16 = u.index(u.startIndex, offsetBy: startUTF16, limitedBy: u.endIndex),
              let e16 = u.index(u.startIndex, offsetBy: endUTF16, limitedBy: u.endIndex),
              let start = s16.samePosition(in: text),
              let end = e16.samePosition(in: text) else { return nil }
        return String(text[start..<end])
    }
}

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

                // The comment body sits below the username/time header line,
                // with any inline bold/italic/size formatting applied (#318).
                Text(TextFormatting.attributedComment(comment.body, spans: comment.formatting, baseSize: TextFormatting.commentBaseSize))
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
