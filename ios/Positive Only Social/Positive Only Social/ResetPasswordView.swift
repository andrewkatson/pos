//
//  ResetPasswordView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/21/25.
//

import SwiftUI

// Handles the 'reset_password' flow.
struct ResetPasswordView: View {
    var usernameOrEmail: String
    var resetToken: String

    // MARK: Envrionment Properties
    @EnvironmentObject var authManager: AuthenticationManager
    
    @State private var username: String = ""
    @State private var email: String = ""
    @State private var newPassword: String = ""
    
    // State matching your template
    @State private var isLoading: Bool = false
    @State private var errorMessage: String = ""
    @State private var showingErrorAlert: Bool = false
    
    // The new API service
    let api: Networking
    let keychainHelper: KeychainHelperProtocol
    
    var body: some View {
        ZStack {
            Form {
                Section(header: Text("Confirm Credentials")) {
                    TextField("Username", text: $username)
                        .autocapitalization(.none)
                        .accessibilityIdentifier("UsernameTextField")
                    TextField("Email", text: $email)
                        .keyboardType(.emailAddress)
                        .autocapitalization(.none)
                        .accessibilityIdentifier("EmailTextField")
                }
                
                Section(header: Text("Set New Password")) {
                    SecureField("New Password", text: $newPassword)
                        .accessibilityIdentifier("NewPasswordSecureField")
                }
                
                Button("Reset Password and Login") {
                    Task {
                        await performReset()
                    }
                }
                .disabled(username.isEmpty || email.isEmpty || newPassword.isEmpty || isLoading)
                .accessibilityIdentifier("ResetPasswordAndLoginButton")
            }
            .navigationTitle("Set New Password")
            .onAppear {
                if usernameOrEmail.contains("@") {
                    self.email = usernameOrEmail
                } else {
                    self.username = usernameOrEmail
                }
            }
            
            if isLoading {
                ProgressView().progressViewStyle(.circular).scaleEffect(2)
            }
        }
        .alert("Error", isPresented: $showingErrorAlert, presenting: errorMessage) { _ in
            Button("OK") { }
        } message: { message in
            Text(message)
        }
    }
    
    // --- API Call (Refactored) ---
    private func performReset() async {
        isLoading = true
        
        do {
            _ = try await api.resetPassword(
                username: username,
                email: email,
                newPassword: newPassword,
                resetToken: resetToken
            )
            
            print("✅ Password reset successful. Attempting auto-login...")

            // 2. IMMEDIATELY Log in with the new password
            let loginData = try await api.loginUser(
                usernameOrEmail: username.isEmpty ? email : username,
                password: newPassword,
                rememberMe: "false",
                ip: "127.0.0.1"
            )

            // 3. Decode the Login Response
            let loginDetails = try JSONDecoder().decode(LoginResponseFields.self, from: loginData)
            
            // 4. Update AuthManager
            // This is the magic trigger that swaps the view to HomeView
            guard let userId = loginDetails.userId else {
                throw NSError(domain: "ResetPasswordError", code: 0, userInfo: [NSLocalizedDescriptionKey: "Password reset failed: server did not return a user ID."])
            }

            let userSession = UserSession(
                sessionToken: loginDetails.sessionManagementToken,
                username: username,
                userId: userId,
                isIdentityVerified: false
            )
            
            // Run on Main Actor to update UI
            await MainActor.run {
                authManager.login(with: userSession)
                isLoading = false
            }
            
            print("✅ Auto-login successful. View should swap now.")
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? "An unknown error occurred."
            showingErrorAlert = true
            print("🔴 Password reset failed: \(error)")
            isLoading = false
        }
    }
}

#Preview {
    ResetPasswordView(usernameOrEmail: "test", resetToken: "", api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper).environmentObject(PreviewHelpers.authManager)
}
