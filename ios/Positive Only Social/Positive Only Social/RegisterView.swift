//
//  Register.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/6/25.
//

import SwiftUI

import SwiftUI

struct RegisterView: View {
    // Dependencies passed from the parent view
    let api: APIProtocol
    
    // MARK: Envrionment Properties
    @EnvironmentObject var authManager: AuthenticationManager
    
    @Binding var path: NavigationPath

    // MARK: - State Properties
    @State private var username = ""
    @State private var email = ""
    @State private var password = ""
    @State private var confirmPassword = ""

    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingErrorAlert = false
    
    // Unique identifiers for Keychain
    private let keychainService = "positive-only-social.Positive-Only-Social" // CHANGE to your app's bundle ID
    private let sessionAccount = "userSessionToken"

    // MARK: - Computed Properties for Validation
    private var isPasswordMatching: Bool {
        // Don't show an error if confirm password field is empty
        if confirmPassword.isEmpty {
            return true
        }
        return password == confirmPassword
    }
    
    private var isFormValid: Bool {
        !username.isEmpty && !email.isEmpty && !password.isEmpty && password == confirmPassword
    }

    // MARK: - View Body
    var body: some View {
        VStack(spacing: 15) {
            Text("Create Account")
                .font(.largeTitle).fontWeight(.bold)
                .padding(.bottom, 20)

            // MARK: - Input Fields
            TextField("Username", text: $username)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(10)
                .textContentType(.username)
                .autocapitalization(.none)

            TextField("Email", text: $email)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(10)
                .textContentType(.emailAddress)
                .autocapitalization(.none)
                .keyboardType(.emailAddress)

            SecureField("Password", text: $password)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(10)
                .textContentType(.newPassword)

            SecureField("Confirm Password", text: $confirmPassword)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(10)
                .textContentType(.newPassword)
            
            // Real-time password mismatch warning
            if !isPasswordMatching {
                Text("Passwords do not match.")
                    .font(.caption)
                    .foregroundColor(.red)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            Spacer()

            // MARK: - Register Button
            if isLoading {
                ProgressView()
            } else {
                Button(action: register) {
                    Text("Register")
                        .font(.headline)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                        .padding()
                        .frame(maxWidth: .infinity)
                        .background(isFormValid ? Color.blue : Color.gray)
                        .cornerRadius(12)
                }
                .disabled(!isFormValid)
            }
        }
        .padding()
        .navigationTitle("Register")
        .navigationBarTitleDisplayMode(.inline)
        .alert("Registration Failed", isPresented: $showingErrorAlert) {
            Button("OK") { }
        } message: {
            Text(errorMessage ?? "An unknown error occurred.")
        }
    }

    // MARK: - Registration Action
    private func register() {
        Task {
            isLoading = true
            do {
                let responseData = try await api.register(
                    username: username,
                    email: email,
                    password: password,
                    rememberMe: "false", // We don't need remember me on registration
                    ip: "127.0.0.1"
                )

                // Decode the response to get the session token
                let decoder = JSONDecoder()
                let wrapper = try decoder.decode(APIWrapperResponse.self, from: responseData)
                guard let innerData = wrapper.responseList.data(using: .utf8) else {
                    throw URLError(.cannotDecodeContentData)
                }
                let loginResponseArray = try decoder.decode([DjangoLoginResponseObject].self, from: innerData)
                guard let loginDetails = loginResponseArray.first?.fields else {
                    throw URLError(.cannotDecodeContentData)
                }

                // Securely save the new session token to the Keychain
                try KeychainHelper.shared.save(
                    loginDetails.sessionManagementToken,
                    for: keychainService,
                    account: sessionAccount
                )
                
                authManager.login()

                print("✅ Registration successful. Session token stored.")

                // Navigate to Home, replacing the stack so the user can't go back.
                path = NavigationPath(["HomeView"])

            } catch {
                errorMessage = "This username or email may already be taken. Please try again."
                showingErrorAlert = true
                print("🔴 Registration failed: \(error)")
            }
            isLoading = false
        }
    }
}


// MARK: - Preview
#Preview {
    // Provide a constant binding for the preview to work
    @Previewable @State var path = NavigationPath()
    
    return NavigationStack(path: $path) {
        RegisterView(api: StatefulStubbedAPI(), path: $path)
    }
}
