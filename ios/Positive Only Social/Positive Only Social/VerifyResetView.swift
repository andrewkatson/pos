//
//  VerifyResetView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/21/25.
//

import SwiftUI
import Combine

// Handles the 'verify_reset' flow.
struct VerifyResetView: View {
    var usernameOrEmail: String
    @State private var pin: String = ""
    @State private var didVerifySuccessfully: Bool = false
    
    // State matching your template
    @State private var isLoading:Bool = false
    @State private var errorMessage: String = ""
    @State private var showingErrorAlert: Bool = false
    
    // The new API service
    let api: APIProtocol
    let keychainHelper: KeychainHelperProtocol
    
    var body: some View {
        ZStack {
            Form {
                Section(header: Text("Verify Your Identity")) {
                    Text("Enter the 6-digit PIN sent to \(usernameOrEmail).")
                        .font(.callout)
                    
                    TextField("6-Digit PIN", text: $pin)
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
            ResetPasswordView(usernameOrEmail: usernameOrEmail, api: api, keychainHelper: keychainHelper)
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
            let responseData = try await api.verifyPasswordReset(usernameOrEmail: usernameOrEmail, resetID: resetID)
            
            _ = try JSONDecoder().decode(APIWrapperResponse.self, from: responseData)
            
            print("✅ PIN verification successful.")

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
    VerifyResetView(usernameOrEmail: "test", api: StatefulStubbedAPI(), keychainHelper: KeychainHelper())
}
