//
//  VerifyResetView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/21/25.
//

import SwiftUI
import Combine

private struct VerifyResetResponse: Decodable {
    let reset_token: String?
}

// Handles the 'verify_reset' flow.
struct VerifyResetView: View {
    // MARK: Envrionment Properties
    @EnvironmentObject var authManager: AuthenticationManager

    var usernameOrEmail: String
    @State private var verificationToken: String = ""
    @State private var didVerifySuccessfully: Bool = false
    @State private var resetToken: String = ""

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
                Section(header: Text("Verify Your Identity")) {
                    Text("Enter the verification token sent to \(usernameOrEmail).")
                        .font(.callout)

                    TextField("Verification Token", text: $verificationToken)
                        .accessibilityIdentifier("VerificationTokenTextField")
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                }

                Button("Verify") {
                    Task {
                        await performVerifyReset()
                    }
                }
                .disabled(verificationToken.isEmpty || isLoading)
                .accessibilityIdentifier("VerifyButton")
            }
            .navigationTitle("Enter Verification Token")

            if isLoading {
                ProgressView().progressViewStyle(.circular).scaleEffect(2)
            }
        }
        .alert("Error", isPresented: $showingErrorAlert, presenting: errorMessage) { _ in
            Button("OK") { }
        } message: { message in
            Text(message)
        }
        .navigationDestination(isPresented: $didVerifySuccessfully) {
            ResetPasswordView(usernameOrEmail: usernameOrEmail, resetToken: resetToken, api: api, keychainHelper: keychainHelper).environmentObject(authManager)
        }
    }

    // --- API Call (Refactored) ---
    private func performVerifyReset() async {
        isLoading = true

        do {
            let data = try await api.verifyPasswordReset(usernameOrEmail: usernameOrEmail, verificationToken: verificationToken)
            let response = try JSONDecoder().decode(VerifyResetResponse.self, from: data)
            guard let token = response.reset_token else {
                errorMessage = "Verification failed: no reset token received."
                showingErrorAlert = true
                isLoading = false
                return
            }

            print("✅ Verification successful.")

            resetToken = token
            isLoading = false
            didVerifySuccessfully = true

        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? "Invalid token or an unknown error occurred."
            showingErrorAlert = true
            print("🔴 Verification failed: \(error)")
            isLoading = false
        }
    }
}

#Preview {
    VerifyResetView(usernameOrEmail: "test", api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper).environmentObject(PreviewHelpers.authManager)
}
