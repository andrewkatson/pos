//
//  PushNotifications.swift
//  Positive Only Social
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

    /// A notification was tapped — route to the rejected post if it carries one.
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        routeIfPostRejection(userInfo: response.notification.request.content.userInfo)
        completionHandler()
    }

    /// Show the banner + play the sound even while the app is foregrounded, so a
    /// rejection surfaces instead of being silently dropped.
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound])
    }

    /// Pull `post_identifier` out of the payload's `data` map (the shape the
    /// backend sends under the APNs `data` key) and hand it to the router. Gated
    /// on the `type` tag so only a post-rejection push routes to a post — any
    /// future push kind is ignored here rather than mis-routed.
    private func routeIfPostRejection(userInfo: [AnyHashable: Any]) {
        guard let data = userInfo["data"] as? [String: Any],
              data["type"] as? String == PUSH_TYPE_POST_REJECTED,
              let postIdentifier = data["post_identifier"] as? String else {
            return
        }
        DispatchQueue.main.async {
            PushRouter.shared.openPost(postIdentifier)
        }
    }
}

// The machine-readable `type` on a rejection push's data map, mirroring the
// backend's PUSH_TYPE_POST_REJECTED (user_system/constants.py).
private let PUSH_TYPE_POST_REJECTED = "post_rejected"
