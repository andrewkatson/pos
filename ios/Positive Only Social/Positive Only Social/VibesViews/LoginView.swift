import SwiftUI

struct LoginView: View {
    let api: Networking
    let keychainHelper: KeychainHelperProtocol

    // MARK: Environment Properties
    @EnvironmentObject var authManager: AuthenticationManager

    // MARK: - State Properties
    @State private var usernameOrEmail = ""
    @State private var password = ""
    @State private var rememberMe = false
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingErrorAlert = false

    // MARK: - Two-Factor State (issue #348)
    // Set when login answered with a challenge instead of a session; the login
    // form is replaced by the code-entry step until the challenge is exchanged
    // (or the user goes back).
    @State private var twoFactorChallengeToken: String?
    @State private var twoFactorCode = ""
    @State private var useRecoveryCode = false

    // Which field currently owns the keyboard. Cleared (set to nil) to dismiss
    // the keyboard through SwiftUI's focus system — the only dismissal that
    // sticks; see KeyboardDismiss.swift (issue #205).
    private enum Field: Hashable { case usernameOrEmail, password, twoFactorCode }
    @FocusState private var focusedField: Field?


    // Unique identifiers for Keychain items
    private let keychainService = GVOAppConstants.keychainService
    private let sessionAccount = "userSessionToken"
    private let rememberMeAccount = "userRememberMeTokens"

    // Authenticator codes are 6 digits; recovery codes are 10 hex characters
    // (backend/user_system/constants.py Patterns).
    private var isTwoFactorCodeValid: Bool {
        let trimmed = twoFactorCode.trimmingCharacters(in: .whitespaces)
        if useRecoveryCode {
            return trimmed.count == 10 && trimmed.lowercased().allSatisfy { "0123456789abcdef".contains($0) }
        }
        return trimmed.count == 6 && trimmed.allSatisfy(\.isNumber)
    }

    // MARK: - View Body
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "lock.shield.fill").font(.system(size: 80)).foregroundColor(.blue)
                // Let taps on this decorative icon fall through to the
                // container's dismiss-keyboard gesture (issue #205).
                .allowsHitTesting(false)
            if twoFactorChallengeToken != nil {
                twoFactorSection
            } else {
                loginSection
            }
            Spacer()
        }
        .padding()
        .dismissKeyboardOnTap { focusedField = nil }
        .onSubmit { focusedField = nil }
        .navigationTitle(twoFactorChallengeToken != nil ? "Two-Factor Login" : "Login")
        .navigationDestination(for: String.self) { routeName in if routeName == "RequestResetView" { RequestResetView(api: api, keychainHelper: keychainHelper) } }
        .alert("Login Failed", isPresented: $showingErrorAlert) { Button("OK") {}.accessibilityIdentifier("LoginFailedOkButton") } message: { Text(errorMessage ?? "An unknown error occurred.") }
    }

    @ViewBuilder
    private var loginSection: some View {
        // Under UI testing, drop the credential content types on both fields:
        // a `.username`/`.password` pairing makes iOS surface the AutoFill /
        // strong-password QuickType panel, which steals focus and breaks typing.
        TextField("Username or Email", text: $usernameOrEmail).padding().background(Color(.systemGray6)).cornerRadius(10).textContentType(isUITesting() ? nil : .username).autocapitalization(.none).keyboardType(.emailAddress)
            .focused($focusedField, equals: .usernameOrEmail)
            .accessibilityIdentifier("UsernameOrEmailTextField")
        SecureField("Password", text: $password).padding().background(Color(.systemGray6)).cornerRadius(10).textContentType(isUITesting() ? nil : .password)
            .focused($focusedField, equals: .password)
            .accessibilityIdentifier("PasswordSecureField")
        Toggle("Remember Me", isOn: $rememberMe)
            .accessibilityIdentifier("RememberMeToggle")
        if isLoading { ProgressView().padding() } else {
            Button(action: login) { Text("Login").font(.headline).fontWeight(.semibold).foregroundColor(.white).padding().frame(maxWidth: .infinity).background(usernameOrEmail.isEmpty || password.isEmpty ? Color.gray : Color.blue).cornerRadius(12) }.disabled(usernameOrEmail.isEmpty || password.isEmpty).accessibilityIdentifier("LoginButton")
        }
        NavigationLink(value: "RequestResetView") {
            Text("Forgot Password?")
        }
        .frame(maxWidth: .infinity, alignment: .trailing)
        .accessibilityIdentifier("ForgotPasswordButton")
    }

    @ViewBuilder
    private var twoFactorSection: some View {
        Text(useRecoveryCode
             ? "Enter one of your recovery codes. Each code works only once."
             : "Enter the 6-digit code from your authenticator app.")
            .font(.subheadline)
            .foregroundColor(.secondary)
            .multilineTextAlignment(.center)
        TextField(useRecoveryCode ? "Recovery Code" : "Authenticator Code", text: $twoFactorCode)
            .padding().background(Color(.systemGray6)).cornerRadius(10)
            .textContentType(.oneTimeCode)
            .keyboardType(useRecoveryCode ? .asciiCapable : .numberPad)
            .autocapitalization(.none)
            .focused($focusedField, equals: .twoFactorCode)
            .accessibilityIdentifier("TwoFactorCodeTextField")
        if isLoading { ProgressView().padding() } else {
            Button(action: verifyTwoFactorCode) { Text("Verify").font(.headline).fontWeight(.semibold).foregroundColor(.white).padding().frame(maxWidth: .infinity).background(isTwoFactorCodeValid ? Color.blue : Color.gray).cornerRadius(12) }.disabled(!isTwoFactorCodeValid).accessibilityIdentifier("VerifyTwoFactorButton")
        }
        Button(useRecoveryCode ? "Use an authenticator code instead" : "Use a recovery code instead") {
            useRecoveryCode.toggle()
            twoFactorCode = ""
        }
        .disabled(isLoading)
        .accessibilityIdentifier("ToggleRecoveryCodeButton")
        Button("Back to login") {
            twoFactorChallengeToken = nil
            twoFactorCode = ""
            useRecoveryCode = false
        }
        // Disabled while a verification request is in flight so the task can't
        // complete and log the user in after they've navigated back.
        .disabled(isLoading)
        .accessibilityIdentifier("BackToLoginButton")
    }

    // MARK: - Updated Login Action
    private func login() {
        Task {
            isLoading = true
            do {
                let responseData = try await api.loginUser(usernameOrEmail: usernameOrEmail, password: password, rememberMe: String(rememberMe), ip: "127.0.0.1")

                // A 2FA-enrolled account answers with a challenge, not a
                // session; swap to the code-entry step (issue #348).
                if let challenge = try? JSONDecoder().decode(TwoFactorRequiredFields.self, from: responseData),
                   challenge.twoFactorRequired {
                    twoFactorChallengeToken = challenge.challengeToken
                    twoFactorCode = ""
                    isLoading = false
                    return
                }

                let loginDetails = try JSONDecoder().decode(LoginResponseFields.self, from: responseData)
                try completeLogin(with: loginDetails)
            } catch let error as APIError {
                handleLoginError(error)
            } catch {
                errorMessage = "Login failed. Please check your credentials and try again."
                showingErrorAlert = true
                NSLog("%@", "🔴 Login failed with error: \(error)")
            }
            isLoading = false
        }
    }

    // MARK: - Two-Factor Verify Action
    private func verifyTwoFactorCode() {
        guard let challengeToken = twoFactorChallengeToken else { return }
        Task {
            isLoading = true
            do {
                let trimmed = twoFactorCode.trimmingCharacters(in: .whitespaces)
                let responseData = try await api.loginUser2FA(
                    challengeToken: challengeToken,
                    totpCode: useRecoveryCode ? nil : trimmed,
                    // Recovery codes are sent lowercased to match the backend pattern.
                    recoveryCode: useRecoveryCode ? trimmed.lowercased() : nil,
                    ip: "127.0.0.1"
                )
                let loginDetails = try JSONDecoder().decode(LoginResponseFields.self, from: responseData)
                try completeLogin(with: loginDetails)
            } catch let error as APIError {
                if case .serverError(_, let message) = error, message == GVOAppConstants.invalidTwoFactorChallengeError {
                    // The challenge timed out (or was invalidated): start over
                    // from the default authenticator-code entry.
                    twoFactorChallengeToken = nil
                    twoFactorCode = ""
                    useRecoveryCode = false
                    errorMessage = "Your login expired. Please sign in again."
                    showingErrorAlert = true
                } else {
                    handleLoginError(error)
                }
            } catch {
                errorMessage = "Verification failed. Please try again."
                showingErrorAlert = true
                NSLog("%@", "🔴 Two-factor login failed with error: \(error)")
            }
            isLoading = false
        }
    }

    /// Shared tail of both login steps: persist the session and tokens.
    private func completeLogin(with loginDetails: LoginResponseFields) throws {
        guard let userId = loginDetails.userId else {
            throw NSError(domain: "LoginError", code: 0, userInfo: [NSLocalizedDescriptionKey: "Login failed: server did not return a user ID."])
        }

        // MARK: - Securely Store Token in Keychain
        authManager.login(with: UserSession(sessionToken: loginDetails.sessionManagementToken, username: loginDetails.username ?? usernameOrEmail, userId: userId, isIdentityVerified: false))

        NSLog("%@", "✅ Session token securely saved to Keychain.")

        // Store "Remember Me" tokens if they exist and toggle is on
        if rememberMe, let seriesId = loginDetails.seriesIdentifier, let cookieToken = loginDetails.loginCookieToken {
            // We can store a simple struct for these tokens
            struct RememberMeTokens: Codable { let seriesId: String; let cookieToken: String }
            let tokens = RememberMeTokens(seriesId: seriesId, cookieToken: cookieToken)
            try keychainHelper.save(tokens, for: keychainService, account: rememberMeAccount)
            NSLog("%@", "🔑 Remember Me tokens saved to Keychain.")
        } else {
            // If "Remember Me" is off, ensure any old tokens are deleted.
            try keychainHelper.delete(service: keychainService, account: rememberMeAccount)
        }
    }

    private func handleLoginError(_ error: APIError) {
        if error.isAccountBanned {
            errorMessage = GVOAppConstants.accountSuspendedMessage
        } else if error.isEmailNotVerified {
            errorMessage = GVOAppConstants.emailNotVerifiedMessage
        } else if case .serverError(_, let message) = error {
            errorMessage = message
        } else {
            // Transport/status-code failures (timeouts, 5xx) aren't a
            // credentials problem — show what actually went wrong.
            errorMessage = error.userFacingMessage
        }
        showingErrorAlert = true
        NSLog("%@", "🔴 Login failed with error: \(error)")
    }
}

#Preview {
    LoginView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper).environmentObject(PreviewHelpers.authManager)
}
