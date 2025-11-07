//
//  SettingsView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/8/25.
//

import SwiftUI

struct SettingsView: View {
    // The AuthenticationManager is still needed to trigger the final UI change.
    @EnvironmentObject private var authManager: AuthenticationManager
    
    // The ViewModel manages the state and logic for this view.
    @StateObject private var viewModel: SettingsViewModel
    
    init(api: APIProtocol, keychainHelper: KeychainHelperProtocol) {
        _viewModel = StateObject(wrappedValue: SettingsViewModel(api: api, keychainHelper: keychainHelper))
    }
    
    var body: some View {
        NavigationStack {
            List {
                // MARK: - Logout Section
                Section {
                    Button(role: .destructive) {
                        // Show the confirmation alert before proceeding
                        viewModel.showingLogoutConfirm = true
                    } label: {
                        Text("Logout")
                    }
                }
                
                // MARK: - Delete Account Section
                Section(header: Text("Account Actions")) {
                    Button(role: .destructive) {
                        // Show the delete confirmation alert
                        viewModel.showingDeleteConfirm = true
                    } label: {
                        Text("Delete Account")
                            .foregroundColor(.red)
                    }
                }
            }
            .navigationTitle("Settings")
            // MARK: - Confirmation Alerts
            .alert("Are you sure you want to log out?", isPresented: $viewModel.showingLogoutConfirm) {
                Button("Cancel", role: .cancel) { }
                Button("Logout", role: .destructive) {
                    viewModel.logout(authManager: authManager)
                }
            }
            .alert("Delete Your Account?", isPresented: $viewModel.showingDeleteConfirm) {
                Button("Cancel", role: .cancel) { }
                Button("Delete", role: .destructive) {
                    viewModel.deleteAccount(authManager: authManager)
                }
            } message: {
                Text("This action is permanent and cannot be undone.")
            }
            .alert("Error", isPresented: $viewModel.showingErrorAlert) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(viewModel.errorMessage)
            }
        }
    }
}

#Preview {
    // The preview needs the authManager in its environment to work correctly.
    SettingsView(api: StatefulStubbedAPI(), keychainHelper: KeychainHelper())
        .environmentObject(AuthenticationManager())
}
