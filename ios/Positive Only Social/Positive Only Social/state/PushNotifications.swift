//
//  PushNotifications.swift
//  Vibes
//
//  APNs registration + notification handling (issues #342/#343).
//

import Foundation
import UIKit
import UserNotifications

/// Owns the device's push lifecycle: ask for permission, register with APNs,
/// upload the token to the backend, and route a tapped notification to the
/// rejected post. Best-effort throughout — a denied permission, a missing
/// session, or a failed upload just leaves the user relying on in-app
/// reconciliation (#282), so nothing here ever surfaces an error to the user.
///
/// A singleton because the APNs callbacks arrive on the `UIApplicationDelegate`
/// and the permission request comes from the home screen; both funnel here.
final class PushNotifications: NSObject, UNUserNotificationCenterDelegate {
    static let shared = PushNotifications()

    private let api: Networking = Config.api
    private let keychainHelper: KeychainHelperProtocol = KeychainHelper()
    private let account = "userSessionToken"

    /// The most recent APNs token, kept so it can be (re)uploaded once a session
    /// exists — the token can arrive before the user has logged in.
    private var cachedToken: String?

    private override init() { super.init() }

    /// Become the notification-center delegate. Called once at launch so a tap
    /// routes even when the app was cold-started by the notification.
    func configure() {
        UNUserNotificationCenter.current().delegate = self
    }

    /// Ask for notification permission and, if granted, register with APNs. Safe
    /// to call whenever the home screen appears — iOS only prompts once, and a
    /// re-register just refreshes the token.
    func requestAuthorizationAndRegister() {
        // Never trigger the system permission dialog under UI tests: it would
        // interrupt unrelated UI-test flows navigating the app. Checked inline
        // (same arg as isUITesting()) to avoid referencing that free function
        // across the test-target membership boundary.
        if CommandLine.arguments.contains("--ui_testing") { return }
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { granted, _ in
            guard granted else { return }
            DispatchQueue.main.async {
                UIApplication.shared.registerForRemoteNotifications()
            }
        }
    }

    /// APNs handed us a device token: hex-encode it, cache it, and upload it.
    func handleDeviceToken(_ deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        cachedToken = token
        uploadToken(token)
    }

    /// Re-upload the cached token — e.g. right after login, when a token that
    /// arrived before the session existed can finally be registered.
    func uploadCachedTokenIfAvailable() {
        if let token = cachedToken { uploadToken(token) }
    }

    private func uploadToken(_ token: String) {
        guard let session = try? keychainHelper.load(
            UserSession.self, from: GVOAppConstants.keychainService, account: account) else {
            return
        }
        Task {
            do {
                _ = try await api.registerDevice(
                    sessionManagementToken: session.sessionToken, platform: "ios", token: token)
            } catch {
                // Best-effort: push is never the source of truth (#282).
            }
        }
    }

    // MARK: - UNUserNotificationCenterDelegate

    /// A notification was tapped — route to what it is about, if anything.
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        route(userInfo: response.notification.request.content.userInfo)
        completionHandler()
    }

    /// Show the banner + play the sound even while the app is foregrounded, so a
    /// rejection surfaces instead of being silently dropped.
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound])
    }

    /// Route a tapped notification by its payload's `data` map (the shape the
    /// backend sends under the APNs `data` key), gated on the `type` tag so only
    /// known kinds route anywhere and any future kind is ignored rather than
    /// mis-routed: the post kinds (a rejection, a new post, a comment or a like
    /// — #342/#444) open their `post_identifier`; a follow request opens the
    /// follow-request list, and a new follower that follower's profile (#604).
    private func route(userInfo: [AnyHashable: Any]) {
        // APNs bridges the nested JSON object as [AnyHashable: Any] (from
        // NSDictionary), so cast to that — [String: Any] can fail on a valid
        // payload and silently drop the tap.
        guard let data = userInfo["data"] as? [AnyHashable: Any],
              let type = data["type"] as? String else {
            return
        }
        if POST_PUSH_TYPES.contains(type), let postIdentifier = data["post_identifier"] as? String {
            DispatchQueue.main.async { PushRouter.shared.openPost(postIdentifier) }
        } else if type == FOLLOW_REQUEST_PUSH_TYPE {
            DispatchQueue.main.async { PushRouter.shared.openFollowRequests() }
        } else if type == NEW_FOLLOWER_PUSH_TYPE, let username = data["username"] as? String, !username.isEmpty {
            DispatchQueue.main.async { PushRouter.shared.openProfile(username) }
        }
    }
}

// The machine-readable `type`s on a push's data map that carry a post to open,
// mirroring the backend's PUSH_TYPE_* kinds (user_system/constants.py).
private let POST_PUSH_TYPES: Set<String> = ["post_rejected", "new_post", "new_comment", "new_like"]
// Follow kinds (#604), which carry a `username` instead of a post.
private let FOLLOW_REQUEST_PUSH_TYPE = "follow_request"
private let NEW_FOLLOWER_PUSH_TYPE = "new_follower"
