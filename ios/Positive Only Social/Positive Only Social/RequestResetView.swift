//
//  RequestResetView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/21/25.
//

import SwiftUI

// Handles the 'request_reset' flow.
struct RequestResetView: View {
    @State private var usernameOrEmail: String = ""
    @State private var didRequestSuccessfully: Bool = false
    
    // State matching your template
    @State private var isLoading: Bool = false
    @State private var errorMessage: String = ""
    @State private var showingErrorAlert: Bool = false
    
    // The new API service
    let api: APIProtocol
    let keychainHelper: KeychainHelperProtocol
    
    var body: some View {
        ZStack {
            Form {
                Section(header: Text("Find Your Account")) {
                    TextField("Username or Email", text: $usernameOrEmail)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                }
                
                Button("Request Reset") {
                    Task {
                        await performRequestReset()
                    }
                }
                .disabled(usernameOrEmail.isEmpty || isLoading)
            }
            .navigationTitle("Reset Password")
            
            if isLoading {
                ProgressView()
                    .progressViewStyle(.circular)
                    .scaleEffect(2)
            }
        }
        .navigationDestination(isPresented: $didRequestSuccessfully) {
            VerifyResetView(usernameOrEmail: usernameOrEmail, api: api, keychainHelper: keychainHelper)
        }
        .alert("Error", isPresented: $showingErrorAlert, presenting: errorMessage) { _ in
            Button("OK") { }
        } message: { message in
            Text(message)
        }
    }
    
    // --- API Call (Refactored) ---
    private func performRequestReset() async {
        isLoading = true
        // defer { isLoading = false } // A defer block is even cleaner
        
        do {
            let responseData = try await api.requestPasswordReset(usernameOrEmail: usernameOrEmail)
            
            // --- Decoding ---
            // Your example shows a complex decoding process.
            // For this endpoint, we'll just decode the simple success response.
            // You can replace this with your own custom decoding logic.
            let decoder = JSONDecoder()
            _ = try decoder.decode(APIWrapperResponse.self, from: responseData)
            
            print("✅ Reset request successful.")
            
            // Handle success
            isLoading = false
            didRequestSuccessfully = true // This triggers the NavigationLink
            
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? "An unknown error occurred."
            showingErrorAlert = true
            print("🔴 Request reset failed: \(error)")
            isLoading = false
        }
    }
}

#Preview {
    RequestResetView(api: StatefulStubbedAPI(), keychainHelper: KeychainHelper())
}
