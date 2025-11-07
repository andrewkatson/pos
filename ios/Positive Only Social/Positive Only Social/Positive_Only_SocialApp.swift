//
//  Positive_Only_SocialApp.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 8/29/25.
//

import SwiftUI

@main
struct Positive_Only_SocialApp: App {
    // The API client and auth manager are created once and shared.
    @StateObject private var authManager = AuthenticationManager()
    private let api: APIProtocol = Config.api
    private let keychainHelper: KeychainHelperProtocol = KeychainHelper()

    init() {
        // 1. Check if ANY test is running
        let isTesting = ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] != nil

        // 2. Check if a UI Test is running
        let isUITesting = CommandLine.arguments.contains("-ui_testing")

        // 3. It's a Unit Test if (1) is true and (2) is false
        let isUnitTesting = isTesting && !isUITesting

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
