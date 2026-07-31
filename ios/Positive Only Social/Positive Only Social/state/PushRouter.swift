//
//  PushRouter.swift
//  Positive Only Social
//
//  Deep-link target for a tapped push notification (issues #342/#343).
//

import Foundation
import Combine

/// A tiny shared bus the notification handler writes to and the UI observes, so
/// tapping a "post rejected" notification opens that post. Kept separate from
/// the notification plumbing so views depend only on this, not on UIKit/APNs.
///
/// Push is a nudge, never the source of truth (#282 in-app reconciliation is):
/// if nothing observes this — the app is mid-launch, the tab isn't mounted — the
/// pending id is simply cleared and the user still finds the outcome in-app.
final class PushRouter: ObservableObject {
    static let shared = PushRouter()

    /// The identifier of a post a notification asked us to open. Set from the
    /// notification tap; the observing view consumes it and resets it to nil.
    @Published var pendingPostIdentifier: String?

    private init() {}

    func openPost(_ postIdentifier: String) {
        pendingPostIdentifier = postIdentifier
    }
}
