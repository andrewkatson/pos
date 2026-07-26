//
//  ShareActivityView.swift
//  Positive Only Social
//

import SwiftUI
import UIKit

/// Wraps `UIActivityViewController` so a URL can be handed to the iOS native
/// share sheet from SwiftUI (issue #34). The post/comment action menus are
/// `confirmationDialog`s, which can't host a `ShareLink` cleanly, so a menu's
/// "Share" button instead sets a published `ShareURLItem` and this view is
/// presented from a `.sheet(item:)` — the same item-driven pattern the report
/// sheet uses.
struct ShareActivityView: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: [url], applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}

/// A share URL wrapped so it can drive a SwiftUI `.sheet(item:)` (issue #34) —
/// the share-sheet counterpart to the report sheet's `Post` / `CommentViewData`
/// items. A fresh `id` each time means re-sharing the same URL re-presents.
struct ShareURLItem: Identifiable {
    let id = UUID()
    let url: URL
}
