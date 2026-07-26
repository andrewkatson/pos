//
//  CaptionTileView.swift
//  Positive Only Social
//

import SwiftUI

/// The visual stand-in for a text-only post's image (#307): the caption
/// rendered centered on a themed gradient background. Used wherever posts
/// render as image tiles — grids clamp the text via `lineLimit`, the detail
/// view passes nil to show the full caption.
struct CaptionTileView: View {
    let caption: String
    var lineLimit: Int? = 4
    /// Curated caption font + background color keys (issue #318). "default"
    /// keeps the original themed gradient and system font.
    var captionFont: String = "default"
    var backgroundColor: String = "default"

    private let baseCaptionSize = UIFont.preferredFont(forTextStyle: .headline).pointSize

    var body: some View {
        ZStack {
            if let color = TextFormatting.backgroundColor(backgroundColor) {
                color
            } else {
                LinearGradient(
                    colors: [Color.accentColor, Color.accentColor.opacity(0.55)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            }
            Text(caption)
                .font(TextFormatting.captionFont(captionFont, size: baseCaptionSize))
                .foregroundColor(TextFormatting.foregroundColor(backgroundColor) ?? .white)
                .multilineTextAlignment(.center)
                .lineLimit(lineLimit)
                .padding(12)
        }
    }
}

#Preview {
    CaptionTileView(caption: "Words only today — feeling grateful!")
        .frame(width: 200, height: 200)
}
