import SwiftUI

struct LoginView: View {
    let api: Networking
    let keychainHelper: KeychainHelperProtocol
    
    // MARK: Envrionment Properties
    @EnvironmentObject var authManager: AuthenticationManager

    // MARK: - State Properties
    @State private var usernameOrEmail = ""
    @State private var password = ""
    @State private var rememberMe = false
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingErrorAlert = false

    // Which field currently owns the keyboard. Cleared (set to nil) to dismiss
    // the keyboard through SwiftUI's focus system — the only dismissal that
    // sticks; see KeyboardDismiss.swift (issue #205).
    private enum Field: Hashable { case usernameOrEmail, password }
    @FocusState private var focusedField: Field?

    
    // Unique identifiers for Keychain items
    private let keychainService = GVOAppConstants.keychainService
    private let sessionAccount = "userSessionToken"
    private let rememberMeAccount = "userRememberMeTokens"

    // MARK: - View Body
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "lock.shield.fill").font(.system(size: 80)).foregroundColor(.blue)
                // Let taps on this decorative icon fall through to the
                // container's dismiss-keyboard gesture (issue #205).
                .allowsHitTesting(false)
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
            Spacer()
        }
        .padding()
        .dismissKeyboardOnTap { focusedField = nil }
        .onSubmit { focusedField = nil }
        .navigationTitle("Login")
        .navigationDestination(for: String.self) { routeName in if routeName == "RequestResetView" { RequestResetView(api: api, keychainHelper: keychainHelper) } }
        .alert("Login Failed", isPresented: $showingErrorAlert) { Button("OK") {}.accessibilityIdentifier("LoginFailedOkButton") } message: { Text(errorMessage ?? "An unknown error occurred.") }
    }
    
    // MARK: - Updated Login Action
    private func login() {
        Task {
            isLoading = true
            do {
                let responseData = try await api.loginUser(usernameOrEmail: usernameOrEmail, password: password, rememberMe: String(rememberMe), ip: "127.0.0.1")

                let loginDetails = try JSONDecoder().decode(LoginResponseFields.self, from: responseData)

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
                
            } catch let error as APIError {
                if error.isAccountBanned {
                    errorMessage = GVOAppConstants.accountSuspendedMessage
                } else if case .serverError(_, let message) = error {
                    errorMessage = message
                } else {
                    // Transport/status-code failures (timeouts, 5xx) aren't a
                    // credentials problem — show what actually went wrong.
                    errorMessage = error.userFacingMessage
                }
                showingErrorAlert = true
                NSLog("%@", "🔴 Login failed with error: \(error)")
            } catch {
                errorMessage = "Login failed. Please check your credentials and try again."
                showingErrorAlert = true
                NSLog("%@", "🔴 Login failed with error: \(error)")
            }
            isLoading = false
        }
    }
}

#Preview {
    LoginView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper).environmentObject(PreviewHelpers.authManager)
}
