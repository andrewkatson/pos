//
//  CheckEmailView.swift
//  Positive Only Social
//

import SwiftUI

/// Navigation route to the post-registration "check your email" screen,
/// carrying the address the verification link was sent to and — for a brand
/// new account — the member's join number (issue #198), used to welcome them.
struct CheckEmailRoute: Hashable {
    let email: String
    var membershipNumber: Int? = nil
}

/// Shown right after registration: the account exists but cannot log in until
/// the verification link in the welcome email is clicked (issue #237).
struct CheckEmailView: View {
    let api: Networking
    let email: String
    /// The new member's join number (issue #198). Non-nil right after
    /// registration; nil when the screen is reached any other way.
    var membershipNumber: Int? = nil

    @Binding var path: NavigationPath

    @State private var isResending = false
    @State private var resendMessage: String?
    @State private var showingWelcome = false

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "envelope.badge.fill")
                .font(.system(size: 80))
                .foregroundColor(.blue)

            Text("Check Your Email")
                .font(.largeTitle).fontWeight(.bold)

            Text("We sent a verification link to \(email). Click it to activate your account — you won't be able to log in until your email is verified.")
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
                .accessibilityIdentifier("CheckEmailInstructions")

            if let resendMessage = resendMessage {
                Text(resendMessage)
                    .font(.caption)
                    .multilineTextAlignment(.center)
                    .foregroundColor(.secondary)
                    .accessibilityIdentifier("ResendStatusMessage")
            }

            if isResending {
                ProgressView()
            } else {
                Button(action: resend) {
                    Text("Resend Verification Email")
                        .font(.headline).fontWeight(.semibold).foregroundColor(.white)
                        .padding().frame(maxWidth: .infinity)
                        .background(Color.blue).cornerRadius(12)
                }
                .accessibilityIdentifier("ResendVerificationEmailButton")
            }

            Button(action: { path = NavigationPath(["LoginView"]) }) {
                Text("Go to Login")
                    .font(.headline).fontWeight(.semibold).foregroundColor(.white)
                    .padding().frame(maxWidth: .infinity)
                    .background(Color.gray).cornerRadius(12)
            }
            .accessibilityIdentifier("GoToLoginButton")

            Spacer()
        }
        .padding()
        .navigationTitle("Check Your Email")
        .navigationBarTitleDisplayMode(.inline)
        // Registration is complete; going "back" to the form would only invite
        // a duplicate-account error.
        .navigationBarBackButtonHidden(true)
        .onAppear {
            // Greet a brand new member with their join number (issue #198).
            if membershipNumber != nil {
                showingWelcome = true
            }
        }
        .alert("Welcome! 🎉", isPresented: $showingWelcome) {
            Button("OK") { }
        } message: {
            if let membershipNumber {
                Text("You're member #\(membershipNumber)!")
            }
        }
    }

    private func resend() {
        Task {
            isResending = true
            resendMessage = nil
            do {
                _ = try await api.resendVerificationEmail(usernameOrEmail: email)
                resendMessage = "A new verification email is on its way. Check your inbox."
            } catch {
                resendMessage = error.userFacingMessage
            }
            isResending = false
        }
    }
}

#Preview {
    @Previewable @State var path = NavigationPath()

    NavigationStack(path: $path) {
        CheckEmailView(api: PreviewHelpers.api, email: "you@example.com", path: $path)
    }
}
