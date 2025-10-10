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

    var body: some Scene {
        WindowGroup {
            // If logged in, show HomeView. Otherwise, show WelcomeView.
            if authManager.isLoggedIn {
                HomeView(api: api)
                    .environmentObject(authManager) // Make the manager available to all subviews
            } else {
                WelcomeView(api: api)
                    .environmentObject(authManager)
            }
        }
    }
}
