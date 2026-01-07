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
    let api: Networking
    let keychainHelper: KeychainHelperProtocol
    
    // MARK: Envrionment Properties
    @EnvironmentObject var authManager: AuthenticationManager
    
    @Binding var path: NavigationPath

    // MARK: - State Properties
    @State private var username = ""
    @State private var email = ""
    @State private var password = ""
    @State private var confirmPassword = ""
    @State private var dateOfBirth = Date()

    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingErrorAlert = false
    @State private var showingPrivacyPolicy = false
    
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
                .accessibilityIdentifier("UsernameTextField")

            TextField("Email", text: $email)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(10)
                .textContentType(.emailAddress)
                .autocapitalization(.none)
                .keyboardType(.emailAddress)
                .accessibilityIdentifier("EmailTextField")

            SecureField("Password", text: $password)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(10)
                .textContentType(.newPassword)
                .accessibilityIdentifier("PasswordSecureField")
            SecureField("Confirm Password", text: $confirmPassword)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(10)
                .textContentType(.newPassword)
                .accessibilityIdentifier("ConfirmPasswordSecureField")
            
            DatePicker("Date of Birth", selection: $dateOfBirth, displayedComponents: .date)
                .datePickerStyle(.compact)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(10)
                .accessibilityIdentifier("DateOfBirthPicker")
            
            // Real-time password mismatch warning
            if !isPasswordMatching {
                Text("Passwords do not match.")
                    .font(.caption)
                    .foregroundColor(.red)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            Spacer()

            if isLoading {
                ProgressView()
            } else {
                Button(action: { showingPrivacyPolicy = true }) {
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
                .accessibilityIdentifier("RegisterButton")
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
        .alert("Privacy Policy", isPresented: $showingPrivacyPolicy) {
            Button("Ok") {
                register()
            }
            Button("Cancel", role: .cancel) { }
        } message: {
            Text("We collect your username and password for authentication. We do not store your date of birth or any other personal information. We store your posts, comments, and related metadata such as like counts and reports. We also track follower/following relationships and blocked users to maintain the social environment.")
        }
    }

    // MARK: - Registration Action
    private func register() {
        Task {
            isLoading = true
            do {
                let formatter = DateFormatter()
                formatter.dateFormat = "yyyy-MM-dd"
                let dateString = formatter.string(from: dateOfBirth)
                
                let responseData = try await api.register(
                    username: username,
                    email: email,
                    password: password,
                    rememberMe: "false", // We don't need remember me on registration
                    ip: "127.0.0.1",
                    dateOfBirth: dateString
                )

                // Try to decode a backend error first
                struct BackendError: Codable { let error: String }
                if let backendError = try? JSONDecoder().decode(BackendError.self, from: responseData) {
                    errorMessage = backendError.error
                    showingErrorAlert = true
                    isLoading = false
                    return
                }

                // Decode the response to get the session token
                let decoder = JSONDecoder()
                let wrapper = try decoder.decode(APIWrapperResponse.self, from: responseData)
                guard let innerData = wrapper.responseList.data(using: .utf8) else {
                    throw URLError(.cannotDecodeContentData)
                }
                
                let loginResponse = try decoder.decode(DjangoLoginResponseObject.self, from: innerData)
                let loginDetails = loginResponse.fields

                // Securely save the new session token to the Keychain
                authManager.login(with: UserSession(sessionToken: loginDetails.sessionManagementToken, username: username, isIdentityVerified: false))

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
    
    NavigationStack(path: $path) {
        RegisterView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper, path: $path).environmentObject(PreviewHelpers.authManager)
    }
}
