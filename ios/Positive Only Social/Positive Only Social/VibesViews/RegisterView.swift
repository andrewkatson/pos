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

    // Which field currently owns the keyboard. Cleared (set to nil) to dismiss
    // the keyboard through SwiftUI's focus system — the only dismissal that
    // sticks; see KeyboardDismiss.swift (issue #205).
    private enum Field: Hashable { case username, email, password, confirmPassword }
    @FocusState private var focusedField: Field?
    
    // Unique identifiers for Keychain
    private let keychainService = GVOAppConstants.keychainService
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
        AuthRequirements.allMet(AuthRequirements.username(username))
            && !email.isEmpty
            && AuthRequirements.allMet(AuthRequirements.password(password))
            && password == confirmPassword
    }

    // MARK: - View Body
    var body: some View {
        VStack(spacing: 15) {
            Text("Create Account")
                .font(.largeTitle).fontWeight(.bold)
                .padding(.bottom, 20)
                // Let taps on this decorative title fall through to the
                // container's dismiss-keyboard gesture (issue #205).
                .allowsHitTesting(false)

            // MARK: - Input Fields
            TextField("Username", text: $username)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(10)
                // Under UI testing, drop the credential content types (here and on
                // the password fields below). iOS offers "Automatic Strong Passwords"
                // when it recognizes a credential form — a `.username` field followed
                // by a secure field — and that floating QuickType panel steals focus
                // and breaks typing in the UI tests. Nulling `.username` stops iOS
                // from classifying the screen as a sign-up form at all.
                .textContentType(isUITesting() ? nil : .username)
                .autocapitalization(.none)
                .focused($focusedField, equals: .username)
                .accessibilityIdentifier("UsernameTextField")
            if !username.isEmpty {
                RequirementHints(requirements: AuthRequirements.username(username))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 4)
            }

            TextField("Email", text: $email)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(10)
                .textContentType(.emailAddress)
                .autocapitalization(.none)
                .keyboardType(.emailAddress)
                .focused($focusedField, equals: .email)
                .accessibilityIdentifier("EmailTextField")

            SecureField("Password", text: $password)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(10)
                // Disable the automatic "Use Strong Password" AutoFill prompt
                // during UI tests, where it would block interaction. Real users
                // still get the new-password content type.
                .textContentType(isUITesting() ? nil : .newPassword)
                .focused($focusedField, equals: .password)
                .accessibilityIdentifier("PasswordSecureField")
            if !password.isEmpty {
                RequirementHints(requirements: AuthRequirements.password(password))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 4)
            }
            SecureField("Confirm Password", text: $confirmPassword)
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(10)
                .textContentType(isUITesting() ? nil : .newPassword)
                .focused($focusedField, equals: .confirmPassword)
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
        .dismissKeyboardOnTap { focusedField = nil }
        .onSubmit { focusedField = nil }
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
            Text(GVOAppConstants.privacyPolicyText)
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

                let loginDetails = try JSONDecoder().decode(LoginResponseFields.self, from: responseData)

                guard let userId = loginDetails.userId else {
                    throw NSError(domain: "RegisterError", code: 0, userInfo: [NSLocalizedDescriptionKey: "Registration failed: server did not return a user ID."])
                }

                // Securely save the new session token to the Keychain
                authManager.login(with: UserSession(sessionToken: loginDetails.sessionManagementToken, username: username, userId: userId, isIdentityVerified: false))

                NSLog("%@", "✅ Registration successful. Session token stored.")

                // Navigate to Home, replacing the stack so the user can't go back.
                path = NavigationPath(["HomeView"])

            } catch let error as APIError {
                if case .serverError(_, let message) = error {
                    errorMessage = message
                } else {
                    // Transport/status-code failures (timeouts, 5xx) aren't a
                    // duplicate-account problem — show what actually went wrong.
                    errorMessage = error.userFacingMessage
                }
                showingErrorAlert = true
                NSLog("%@", "🔴 Registration failed: \(error)")
            } catch {
                errorMessage = "This username or email may already be taken. Please try again."
                showingErrorAlert = true
                NSLog("%@", "🔴 Registration failed: \(error)")
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
