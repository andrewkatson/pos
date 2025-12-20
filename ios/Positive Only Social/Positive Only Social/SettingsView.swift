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
    @State private var dateOfBirth = Date()
    @State private var showingDatePicker = false
    @State private var showingPrivacyPolicy = false
    
    init(api: APIProtocol, keychainHelper: KeychainHelperProtocol) {
        _viewModel = StateObject(wrappedValue: SettingsViewModel(api: api, keychainHelper: keychainHelper))
    }
    
    var body: some View {
        NavigationStack {
            List {
                // MARK: - Contact Information Section
                Section(header: Text("Contact Information")) {
                    Text("katsonsoftware@gmail.com")
                        .foregroundColor(.gray)
                }

                // MARK: - Logout Section
                Section {
                    Button(role: .destructive) {
                        // Show the confirmation alert before proceeding
                        viewModel.showingLogoutConfirm = true
                    } label: {
                        Text("Logout")
                    }.accessibilityIdentifier("LogoutButton")
                }
                
                // MARK: - Verification Section
                Section {
                    Button {
                        showingDatePicker = true
                    } label: {
                        Text("Verify Identity")
                            .foregroundColor(.blue)
                    }.accessibilityIdentifier("VerifyIdentityButton")
                }
                
                Section {
                    Button {
                        showingPrivacyPolicy = true
                    } label: {
                        Text("Privacy Policy")
                    }.accessibilityIdentifier("PrivacyPolicyButton")
                }
            
                
                // MARK: - Delete Account Section
                Section(header: Text("Account Actions")) {
                    Button(role: .destructive) {
                        // Show the delete confirmation alert
                        viewModel.showingDeleteConfirm = true
                    } label: {
                        Text("Delete Account")
                            .foregroundColor(.red)
                    }.accessibilityIdentifier("DeleteAccountButton")
                }
            }
            .navigationTitle("Settings")
            // MARK: - Confirmation Alerts
            .alert("Are you sure you want to log out?", isPresented: $viewModel.showingLogoutConfirm) {
                Button("Cancel", role: .cancel) { }.accessibilityIdentifier("CancelLogoutButton")
                Button("Logout", role: .destructive) {
                    viewModel.logout(authManager: authManager)
                }.accessibilityIdentifier("ConfirmLogoutButton")
            }
            .alert("Delete Your Account?", isPresented: $viewModel.showingDeleteConfirm) {
                Button("Cancel", role: .cancel) { }.accessibilityIdentifier("CancelDeleteAccountButton")
                Button("Delete", role: .destructive) {
                    viewModel.deleteAccount(authManager: authManager)
                }.accessibilityIdentifier("ConfirmDeleteAccountButton")
            } message: {
                Text("This action is permanent and cannot be undone.")
            }
            .alert("Error", isPresented: $viewModel.showingErrorAlert) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(viewModel.errorMessage)
            }
            .alert("Identity Verified", isPresented: $viewModel.showingVerificationAlert) {
                Button("OK", role: .cancel) { }
            } message: {
                Text(viewModel.verificationMessage)
            }
            .alert("Privacy Policy", isPresented: $showingPrivacyPolicy) {
                Button("Ok", role: .cancel) { }
            } message: {
                Text("We collect your username and password for authentication. We do not store your date of birth or any other personal information. We store your posts, comments, and related metadata such as like counts and reports. We also track follower/following relationships and blocked users to maintain the social environment.")
            }
            .sheet(isPresented: $showingDatePicker) {
                VStack(spacing: 20) {
                    Text("Verify Identity")
                        .font(.headline)
                        .padding(.top)
                    
                    Text("Please enter your date of birth.")
                        .font(.subheadline)
                    
                    DatePicker("Date of Birth", selection: $dateOfBirth, displayedComponents: .date)
                        .datePickerStyle(.wheel)
                        .labelsHidden()
                        .padding()
                    
                    Button("Verify") {
                        showingDatePicker = false
                        viewModel.verifyIdentity(authManager: authManager, dateOfBirth: dateOfBirth)
                    }
                    .padding()
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(8)
                    .accessibilityIdentifier("SubmitVerificationButton")
                    
                    Button("Cancel") {
                        showingDatePicker = false
                    }
                    .foregroundColor(.red)
                }
                .padding()
                .presentationDetents([.medium])
            }
        }
    }
}

#Preview {
    // The preview needs the authManager in its environment to work correctly.
    SettingsView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper)
        .environmentObject(AuthenticationManager())
}
