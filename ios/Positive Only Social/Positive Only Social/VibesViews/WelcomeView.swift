//
//  ContentView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 8/29/25.
//

import SwiftUI

// This enum helps manage the view's state
fileprivate enum AuthState {
    case checking, needsAuth, authenticated
}

struct WelcomeView: View {
    let api: Networking
    let keychainHelper: KeychainHelperProtocol
    
    // MARK: Envrionment Properties
    @EnvironmentObject var authManager: AuthenticationManager

    // State to control the UI
    @State private var authState: AuthState = .checking
    @State private var path = NavigationPath()
    
    // Unique identifiers for Keychain items
    private let keychainService = GVOAppConstants.keychainService
    private let sessionAccount = "userSessionToken"
    private let rememberMeAccount = "userRememberMeTokens"

    var body: some View {
        NavigationStack(path: $path) {
            VStack {
                // The view now switches based on the authentication state
                switch authState {
                case .checking:
                    ProgressView("Checking session...")
                        .scaleEffect(1.5)
                        
                case .needsAuth:
                    NeedsAuthView() // The Login/Register buttons
                    
                case .authenticated:
                    // This state is the trigger to navigate. We show nothing here because
                    // the navigation happens almost instantly.
                    Color.clear
                }
            }
            .navigationTitle("Good Vibes Only")
            // Define all possible navigation destinations
            .navigationDestination(for: String.self) { routeName in
                switch routeName {
                case "LoginView":
                    LoginView(api: api, keychainHelper: keychainHelper).environmentObject(authManager)
                case "RegisterView":
                    RegisterView(api: api, keychainHelper: keychainHelper, path: $path).environmentObject(authManager)
                case "HomeView":
                    HomeView(api: api, keychainHelper: keychainHelper).environmentObject(authManager)
                case "RequestResetView":
                    RequestResetView(api: api, keychainHelper: keychainHelper).environmentObject(authManager)
                default:
                    Text("Unknown Route")
                }
            }
            .navigationDestination(for: CheckEmailRoute.self) { route in
                CheckEmailView(api: api, email: route.email, membershipNumber: route.membershipNumber, path: $path)
            }
        }
        .onAppear(perform: checkRememberMeStatus)
    }

    /// Checks Keychain for tokens and tries to log in automatically.
    private func checkRememberMeStatus() {
        Task {
            // Define a struct to match what we save in the Keychain
            struct RememberMeTokens: Codable { let seriesId: String; let cookieToken: String }
            
            do {
                // 1. Try to load "Remember Me" tokens from Keychain
                guard let tokens = try keychainHelper.load(RememberMeTokens.self, from: keychainService, account: rememberMeAccount) else {
                    // No tokens found, user needs to log in manually.
                    authState = .needsAuth
                    return
                }
                
                // 2. Call the API to log in with the tokens
                let responseData = try await api.loginUserWithRememberMe(
                    sessionManagementToken: "", // Not needed for this call
                    seriesIdentifier: tokens.seriesId,
                    loginCookieToken: tokens.cookieToken,
                    ip: "127.0.0.1"
                )
                
                // 3. Decode the response to get the NEW tokens
                let loginDetails = try JSONDecoder().decode(LoginResponseFields.self, from: responseData)

                // 4. Restore session identity from in-memory state or keychain fallback
                let existingSession = authManager.session
                    ?? (try? keychainHelper.load(UserSession.self, from: keychainService, account: sessionAccount))
                guard let existingSession = existingSession else {
                    throw NSError(domain: "AutoLoginError", code: 0, userInfo: [NSLocalizedDescriptionKey: "No existing session found for remember-me refresh."])
                }
                guard !existingSession.userId.isEmpty else {
                    throw NSError(domain: "AutoLoginError", code: 0, userInfo: [NSLocalizedDescriptionKey: "Stored session has no valid user ID. Please log in again."])
                }
                let userSession = UserSession(sessionToken: loginDetails.sessionManagementToken, username: existingSession.username, userId: existingSession.userId, isIdentityVerified: existingSession.isIdentityVerified)
                authManager.login(with: userSession)
                
                // 5. Update the "Remember Me" tokens in the Keychain with the refreshed cookie token
                if let newCookieToken = loginDetails.loginCookieToken {
                    let newTokens = RememberMeTokens(seriesId: tokens.seriesId, cookieToken: newCookieToken)
                    try keychainHelper.save(newTokens, for: keychainService, account: rememberMeAccount)
                }
                
                NSLog("%@", "✅ Remember Me login successful!")
                // 6. Update state to trigger navigation
                authState = .authenticated
                path.append("HomeView")

            } catch {
                // If anything fails (no tokens, invalid tokens, network error),
                // clear old data and show the manual login screen.
                NSLog("%@", "🔴 Remember Me login failed: \(error.localizedDescription)")
                try? keychainHelper.delete(service: keychainService, account: rememberMeAccount)
                try? keychainHelper.delete(service: keychainService, account: sessionAccount)
                authState = .needsAuth
            }
        }
    }
}


/// A sub-view for showing the Login and Register buttons.
/// This keeps the main WelcomeView body clean.
struct NeedsAuthView: View {
    var body: some View {
        VStack(spacing: 20) {
            Text("Welcome! 👋")
                .font(.largeTitle)
                .fontWeight(.bold)
                .padding(.bottom, 40)

            NavigationLink(value: "LoginView") {
                Text("Login")
                    .font(.headline).fontWeight(.semibold).foregroundColor(.white)
                    .padding().frame(maxWidth: .infinity).background(Color.blue).cornerRadius(12)
                    .accessibilityIdentifier("LoginText")
            }

            NavigationLink(value: "RegisterView") {
                Text("Register")
                    .font(.headline).fontWeight(.semibold).foregroundColor(.white)
                    .padding().frame(maxWidth: .infinity).background(Color.gray).cornerRadius(12)
                    .accessibilityIdentifier("RegisterText")
            }
        }
        .padding()
    }
}


#Preview {
    // You can test different states by passing in a pre-configured stub
    WelcomeView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper)
}
