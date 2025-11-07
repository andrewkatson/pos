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
    
    @State private var username: String = ""
    @State private var email: String = ""
    @State private var newPassword: String = ""
    
    @State private var didResetSuccessfully: Bool = false
    
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
                    TextField("Email", text: $email)
                        .keyboardType(.emailAddress)
                        .autocapitalization(.none)
                }
                
                Section(header: Text("Set New Password")) {
                    SecureField("New Password", text: $newPassword)
                }
                
                Button("Reset Password and Login") {
                    Task {
                        await performReset()
                    }
                }
                .disabled(username.isEmpty || email.isEmpty || newPassword.isEmpty || isLoading)
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
        .navigationDestination(isPresented: $didResetSuccessfully) {
            HomeView(api: api, keychainHelper: keychainHelper)
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
            
            _ = try JSONDecoder().decode(APIWrapperResponse.self, from: responseData)
            
            print("✅ Password reset successful.")

            isLoading = false
            didResetSuccessfully = true // Navigate to Home
            
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? "An unknown error occurred."
            showingErrorAlert = true
            print("🔴 Password reset failed: \(error)")
            isLoading = false
        }
    }
}

#Preview {
    ResetPasswordView(usernameOrEmail: "test", api: StatefulStubbedAPI(), keychainHelper: KeychainHelper())
}
