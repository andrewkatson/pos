//
//  PushRouter.swift
//  Vibes
//
//  Deep-link target for a tapped push notification (issues #342/#343).
//

import Foundation
import Combine

/// A tiny shared bus that writes "open this post" (or "open this profile", or
/// "open your follow requests") requests to the UI. They come from tapping a
/// push notification (a post's: issues #342/#343/#444; the profile of a new
/// follower or of someone who accepted your request, or your follow requests:
/// issue #604), opening a shared
/// `https://smiling.social/post/<id>` link as a Universal Link (issue #382), and
/// opening a shared `/profile/<username>` link the same way (issue #510). Kept
/// separate from all of that plumbing so views depend only on this, not on
/// UIKit/APNs or URL parsing.
///
/// The request parks here until something consumes it, which is what makes a
/// link opened while signed out work: `HomeView` only exists once logged in, so
/// the id waits and routes as soon as it mounts rather than pushing an
/// authenticated screen out of the Welcome flow.
///
/// Push is a nudge, never the source of truth (#282 in-app reconciliation is):
/// if nothing ever observes this the pending id is simply cleared and the user
/// still finds the outcome in-app.
/// The navigation value a routed profile request (a shared link or a follow
/// notification) pushes. Each value is distinct, unlike a `User` for the same
/// username, so it always builds a fresh ProfileView that loads the profile
/// again — after an accepted follow request (issue #604) the posts it now
/// shows must replace the "private" view an already-open copy would keep.
struct OpenedProfileDestination: Hashable {
    let username: String
    let id = UUID()
}

final class PushRouter: ObservableObject {
    static let shared = PushRouter()

    /// The identifier of a post a notification asked us to open. Set from the
    /// notification tap; the observing view consumes it and resets it to nil.
    @Published var pendingPostIdentifier: String?

    /// The username of a profile a shared link asked us to open (issue #510).
    /// Consumed and reset to nil the same way as the post above.
    @Published var pendingProfileUsername: String?

    /// Set when a follow-request notification asked us to open the signed-in
    /// user's incoming follow requests (issue #604). Consumed and reset to
    /// false the same way.
    @Published var pendingFollowRequests = false

    private init() {}

    func openPost(_ postIdentifier: String) {
        pendingPostIdentifier = postIdentifier
    }

    func openProfile(_ username: String) {
        pendingProfileUsername = username
    }

    func openFollowRequests() {
        pendingFollowRequests = true
    }
}
