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

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color.accentColor, Color.accentColor.opacity(0.55)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            Text(caption)
                .font(.headline)
                .foregroundColor(.white)
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
