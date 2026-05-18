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
    @State private var pin: String = ""
    @State private var didVerifySuccessfully: Bool = false
    @State private var resetToken: String = ""
    
    // State matching your template
    @State private var isLoading:Bool = false
    @State private var errorMessage: String = ""
    @State private var showingErrorAlert: Bool = false
    
    // The new API service
    let api: Networking
    let keychainHelper: KeychainHelperProtocol
    
    var body: some View {
        ZStack {
            Form {
                Section(header: Text("Verify Your Identity")) {
                    Text("Enter the 6-digit PIN sent to \(usernameOrEmail).")
                        .font(.callout)
                    
                    TextField("6-Digit PIN", text: $pin)
                        .accessibilityIdentifier("6DigitPinTextField")
                        .keyboardType(.numberPad)
                        .onReceive(Just(pin)) { newValue in
                            let filtered = newValue.filter { "0123456789".contains($0) }
                            if filtered.count > 6 {
                                self.pin = String(filtered.prefix(6))
                            } else {
                                self.pin = filtered
                            }
                        }
                }
                
                Button("Verify") {
                    Task {
                        await performVerifyReset()
                    }
                }
                .disabled(pin.count != 6 || isLoading)
                .accessibilityIdentifier("VerifyButton")
            }
            .navigationTitle("Enter PIN")
            
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
        
        guard let resetID = Int(pin) else {
            errorMessage = "PIN must be numeric."
            showingErrorAlert = true
            isLoading = false
            return
        }
        
        do {
            let data = try await api.verifyPasswordReset(usernameOrEmail: usernameOrEmail, resetID: resetID)
            let response = try JSONDecoder().decode(VerifyResetResponse.self, from: data)
            guard let token = response.reset_token else {
                errorMessage = "Verification failed: no reset token received."
                showingErrorAlert = true
                isLoading = false
                return
            }

            print("✅ PIN verification successful.")

            resetToken = token
            isLoading = false
            didVerifySuccessfully = true // Trigger navigation
            
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? "Invalid PIN or an unknown error occurred."
            showingErrorAlert = true
            print("🔴 PIN verification failed: \(error)")
            isLoading = false
        }
    }
}

#Preview {
    VerifyResetView(usernameOrEmail: "test", api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper).environmentObject(PreviewHelpers.authManager)
}
