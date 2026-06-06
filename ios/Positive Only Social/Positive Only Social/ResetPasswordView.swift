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
    @State private var confirmPassword: String = ""

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
                    if !newPassword.isEmpty {
                        requirementHints(AuthRequirements.password(newPassword))
                    }
                    SecureField("Confirm Password", text: $confirmPassword)
                        .accessibilityIdentifier("ConfirmNewPasswordSecureField")
                    if !confirmPassword.isEmpty && newPassword != confirmPassword {
                        Text("Passwords do not match.")
                            .font(.caption)
                            .foregroundColor(.red)
                    }
                }

                Button("Reset Password and Login") {
                    Task {
                        await performReset()
                    }
                }
                .disabled(username.isEmpty || email.isEmpty || !AuthRequirements.allMet(AuthRequirements.password(newPassword)) || newPassword != confirmPassword || isLoading)
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
    
    // MARK: - Requirement Hints

    @ViewBuilder
    private func requirementHints(_ requirements: [AuthRequirements.Requirement]) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            ForEach(requirements) { requirement in
                requirementHint(requirement.label, met: requirement.met)
            }
        }
    }

    private func requirementHint(_ text: String, met: Bool) -> some View {
        Label(text, systemImage: met ? "checkmark.circle.fill" : "xmark.circle")
            .foregroundColor(met ? .green : .secondary)
            .font(.caption)
            .accessibilityLabel("\(text): \(met ? "met" : "not met")")
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
            
            NSLog("%@", "✅ Password reset successful. Attempting auto-login...")

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
            
            NSLog("%@", "✅ Auto-login successful. View should swap now.")
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? "An unknown error occurred."
            showingErrorAlert = true
            NSLog("%@", "🔴 Password reset failed: \(error)")
            isLoading = false
        }
    }
}

#Preview {
    ResetPasswordView(usernameOrEmail: "test", resetToken: "", api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper).environmentObject(PreviewHelpers.authManager)
}
