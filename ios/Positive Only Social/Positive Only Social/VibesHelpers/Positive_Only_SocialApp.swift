//
//  Positive_Only_SocialApp.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 8/29/25.
//

import SwiftUI
import UIKit

/// Receives the APNs callbacks SwiftUI's `App` can't, forwarding them to
/// `PushNotifications` (issues #342/#343). Registered via the adaptor below.
final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        // Become the notification-center delegate at launch so a tap that
        // cold-starts the app still routes to the rejected post.
        PushNotifications.shared.configure()
        return true
    }

    func application(_ application: UIApplication,
                     didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        PushNotifications.shared.handleDeviceToken(deviceToken)
    }

    func application(_ application: UIApplication,
                     didFailToRegisterForRemoteNotificationsWithError error: Error) {
        // Best-effort: without a token the user just relies on in-app
        // reconciliation (#282). No user-facing error.
    }
}

@main
struct Positive_Only_SocialApp: App {
    // The API client and auth manager are created once and shared.
    @StateObject private var authManager = AuthenticationManager()
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    private let api: Networking = Config.api
    private let keychainHelper: KeychainHelperProtocol = KeychainHelper()

    init() {
        let isUnitTesting = isUnitTesting()

        // Avoid capturing `self` inside StateObject's autoclosure by preparing dependencies first
        let helper: KeychainHelperProtocol = KeychainHelper()
        let manager: AuthenticationManager
        if isUnitTesting {
            // For Unit Tests: Initialize without auto-login
            manager = AuthenticationManager(shouldAutoLogin: false, keychainHelper: helper)
        } else {
            // For Normal Runs AND UI Tests: Let it auto-login normally
            manager = AuthenticationManager(shouldAutoLogin: true, keychainHelper: helper)
        }

        _authManager = StateObject(wrappedValue: manager)
    }
    
    var body: some Scene {
        WindowGroup {
            // If logged in, show HomeView. Otherwise, show WelcomeView.
            if authManager.isLoggedIn {
                HomeView(api: api, keychainHelper: keychainHelper)
                    .environmentObject(authManager) // Make the manager available to all subviews
            } else {
                WelcomeView(api: api, keychainHelper: keychainHelper)
                    .environmentObject(authManager)
            }
        }
    }
}
