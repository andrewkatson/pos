import SwiftUI

struct LoginView: View {
    let api: APIProtocol
    
    // MARK: Envrionment Properties
    @EnvironmentObject var authManager: AuthenticationManager

    // MARK: - State Properties
    @State private var usernameOrEmail = ""
    @State private var password = ""
    @State private var rememberMe = false
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingErrorAlert = false
    
    @State private var path = NavigationPath()
    
    // Unique identifiers for Keychain items
    private let keychainService = "positive-only-social.Positive-Only-Social"
    private let sessionAccount = "userSessionToken"
    private let rememberMeAccount = "userRememberMeTokens"

    // MARK: - View Body
    var body: some View {
        NavigationStack(path: $path) {
            // The VStack with UI elements remains unchanged...
            VStack(spacing: 20) {
                Image(systemName: "lock.shield.fill").font(.system(size: 80)).foregroundColor(.blue)
                TextField("Username or Email", text: $usernameOrEmail).padding().background(Color(.systemGray6)).cornerRadius(10).textContentType(.username).autocapitalization(.none).keyboardType(.emailAddress)
                SecureField("Password", text: $password).padding().background(Color(.systemGray6)).cornerRadius(10).textContentType(.password)
                Toggle("Remember Me", isOn: $rememberMe)
                if isLoading { ProgressView().padding() } else {
                    Button(action: login) { Text("Login").font(.headline).fontWeight(.semibold).foregroundColor(.white).padding().frame(maxWidth: .infinity).background(usernameOrEmail.isEmpty || password.isEmpty ? Color.gray : Color.blue).cornerRadius(12) }.disabled(usernameOrEmail.isEmpty || password.isEmpty)
                }
                Button("Forgot Password?") { print("Forgot Password tapped.") }.frame(maxWidth: .infinity, alignment: .trailing)
                Spacer()
            }
            .padding()
            .navigationTitle("Login")
            .navigationDestination(for: String.self) { routeName in if routeName == "HomeView" { HomeView(api: api) } }
            .alert("Login Failed", isPresented: $showingErrorAlert) { Button("OK") {} } message: { Text(errorMessage ?? "An unknown error occurred.") }
        }
    }
    
    // MARK: - Updated Login Action
    private func login() {
        Task {
            isLoading = true
            do {
                let responseData = try await api.loginUser(usernameOrEmail: usernameOrEmail, password: password, rememberMe: String(rememberMe), ip: "127.0.0.1")
                
                // MARK: Decoding Logic (remains the same)
                let decoder = JSONDecoder()
                let wrapper = try decoder.decode(APIWrapperResponse.self, from: responseData)
                guard let innerData = wrapper.responseList.data(using: .utf8) else { throw URLError(.cannotDecodeContentData) }
                let loginResponseArray = try decoder.decode([DjangoLoginResponseObject].self, from: innerData)
                guard let loginDetails = loginResponseArray.first?.fields else { throw URLError(.cannotDecodeContentData) }
                
                // MARK: - Securely Store Token in Keychain
                try KeychainHelper.shared.save(loginDetails.sessionManagementToken, for: keychainService, account: sessionAccount)
                
                    authManager.login()
                
                print("✅ Session token securely saved to Keychain.")
                
                // Store "Remember Me" tokens if they exist and toggle is on
                if rememberMe, let seriesId = loginDetails.seriesIdentifier, let cookieToken = loginDetails.loginCookieToken {
                    // We can store a simple struct for these tokens
                    struct RememberMeTokens: Codable { let seriesId: String; let cookieToken: String }
                    let tokens = RememberMeTokens(seriesId: seriesId, cookieToken: cookieToken)
                    try KeychainHelper.shared.save(tokens, for: keychainService, account: rememberMeAccount)
                    print("🔑 Remember Me tokens saved to Keychain.")
                } else {
                    // If "Remember Me" is off, ensure any old tokens are deleted.
                    try KeychainHelper.shared.delete(service: keychainService, account: rememberMeAccount)
                }
                
                // On success, navigate to the HomeView.
                path.append("HomeView")
                
            } catch {
                errorMessage = "Login failed. Please check your credentials and try again."
                showingErrorAlert = true
                print("🔴 Login failed with error: \(error)")
            }
            isLoading = false
        }
    }
}

#Preview {
    LoginView(api: StatefulStubbedAPI())
}
