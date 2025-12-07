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
    let api: APIProtocol
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
            // Using the INSECURE method as requested
            let responseData = try await api.resetPassword(
                username: username,
                email: email,
                newPassword: newPassword
            )
            
            // Just check that it didn't throw an error
            _ = try JSONDecoder().decode(APIWrapperResponse.self, from: responseData)
            print("✅ Password reset successful. Attempting auto-login...")
            
            // 2. IMMEDIATELY Log in with the new password
            // This retrieves the session token you need for the HomeView
            let loginData = try await api.loginUser(
                usernameOrEmail: username.isEmpty ? email : username,
                password: newPassword,
                rememberMe: "false",
                ip: "127.0.0.1"
            )
            
            // 3. Decode the Login Response
            let decoder = JSONDecoder()
            let wrapper = try decoder.decode(APIWrapperResponse.self, from: loginData)
            guard let innerData = wrapper.responseList.data(using: .utf8) else { throw URLError(.cannotDecodeContentData) }
            let loginResponse = try decoder.decode(DjangoLoginResponseObject.self, from: innerData)
            let loginDetails = loginResponse.fields
            
            // 4. Update AuthManager
            // This is the magic trigger that swaps the view to HomeView
            let userSession = UserSession(
                sessionToken: loginDetails.sessionManagementToken,
                username: username,
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
    ResetPasswordView(usernameOrEmail: "test", api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper).environmentObject(PreviewHelpers.authManager)
}
