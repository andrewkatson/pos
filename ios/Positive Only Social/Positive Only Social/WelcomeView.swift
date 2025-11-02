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
    let api: APIProtocol
    
    // MARK: Envrionment Properties
    @EnvironmentObject var authManager: AuthenticationManager

    // State to control the UI
    @State private var authState: AuthState = .checking
    @State private var path = NavigationPath()
    
    // Unique identifiers for Keychain items
    private let keychainService = "positive-only-social.Positive-Only-Social"
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
            .navigationTitle("Positive Only Social")
            // Define all possible navigation destinations
            .navigationDestination(for: String.self) { routeName in
                switch routeName {
                case "LoginView":
                    LoginView(api: api)
                case "RegisterView":
                    RegisterView(api: api, path: $path)
                case "HomeView":
                    HomeView(api: api)
                default:
                    Text("Unknown Route")
                }
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
                guard let tokens = try KeychainHelper.shared.load(RememberMeTokens.self, from: keychainService, account: rememberMeAccount) else {
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
                let decoder = JSONDecoder()
                let wrapper = try decoder.decode(APIWrapperResponse.self, from: responseData)
                guard let innerData = wrapper.responseList.data(using: .utf8) else { throw URLError(.cannotDecodeContentData) }
                let loginResponseArray = try decoder.decode([DjangoLoginResponseObject].self, from: innerData)
                guard let loginDetails = loginResponseArray.first?.fields else { throw URLError(.cannotDecodeContentData) }

                // 4. Securely save the new session token
                authManager.login(with: loginDetails.sessionManagementToken)
                
                // 5. Update the "Remember Me" tokens in the Keychain with the refreshed cookie token
                if let newCookieToken = loginDetails.loginCookieToken {
                    let newTokens = RememberMeTokens(seriesId: tokens.seriesId, cookieToken: newCookieToken)
                    try KeychainHelper.shared.save(newTokens, for: keychainService, account: rememberMeAccount)
                }
                
                print("✅ Remember Me login successful!")
                // 6. Update state to trigger navigation
                authState = .authenticated
                path.append("HomeView")

            } catch {
                // If anything fails (no tokens, invalid tokens, network error),
                // clear old data and show the manual login screen.
                print("🔴 Remember Me login failed: \(error.localizedDescription)")
                try? KeychainHelper.shared.delete(service: keychainService, account: rememberMeAccount)
                try? KeychainHelper.shared.delete(service: keychainService, account: sessionAccount)
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
            }

            NavigationLink(value: "RegisterView") {
                Text("Register")
                    .font(.headline).fontWeight(.semibold).foregroundColor(.white)
                    .padding().frame(maxWidth: .infinity).background(Color.gray).cornerRadius(12)
            }
        }
        .padding()
    }
}


#Preview {
    // You can test different states by passing in a pre-configured stub
    WelcomeView(api: StatefulStubbedAPI())
}
