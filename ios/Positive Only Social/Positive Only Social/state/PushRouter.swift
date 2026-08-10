//
//  PushRouter.swift
//  Positive Only Social
//
//  Deep-link target for a tapped push notification (issues #342/#343).
//

import Foundation
import Combine

/// A tiny shared bus that writes "open this post" requests to the UI. Two things
/// produce them: tapping a "post rejected" notification (issues #342/#343), and
/// opening a shared `https://smiling.social/post/<id>` link as a Universal Link
/// (issue #382). Kept separate from both bits of plumbing so views depend only
/// on this, not on UIKit/APNs or URL parsing.
///
/// The request parks here until something consumes it, which is what makes a
/// link opened while signed out work: `HomeView` only exists once logged in, so
/// the id waits and routes as soon as it mounts rather than pushing an
/// authenticated screen out of the Welcome flow.
///
/// Push is a nudge, never the source of truth (#282 in-app reconciliation is):
/// if nothing ever observes this the pending id is simply cleared and the user
/// still finds the outcome in-app.
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
