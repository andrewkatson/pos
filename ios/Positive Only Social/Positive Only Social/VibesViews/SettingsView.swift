//
//  SettingsView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/8/25.
//

import SwiftUI
import UIKit
import CoreImage.CIFilterBuiltins
import UniformTypeIdentifiers

/// How long copied recovery codes stay on the pasteboard before expiring.
private let _recoveryCodeClipboardTTL: TimeInterval = 120

struct SettingsView: View {
    // The AuthenticationManager is still needed to trigger the final UI change.
    @EnvironmentObject private var authManager: AuthenticationManager

    // The ViewModel manages the state and logic for this view.
    @StateObject private var viewModel: SettingsViewModel
    @State private var dateOfBirth = Date()
    @State private var showingDatePicker = false
    @State private var showingPrivacyPolicy = false

    // Two-factor authentication sheets (issue #348).
    @State private var showingEnrollTwoFactor = false
    @State private var showingDisableTwoFactor = false
    @State private var twoFactorConfirmCode = ""
    @State private var twoFactorConfirmPassword = ""
    @State private var disablePassword = ""
    @State private var disableCode = ""
    @State private var disableUsesRecoveryCode = false

    // Change-password sheet (issue #197).
    @State private var showingChangePassword = false
    @State private var changePasswordCurrent = ""
    @State private var changePasswordNew = ""
    @State private var changePasswordConfirm = ""

    /// The support address shown under "Contact Us" (issue #194). Constant,
    /// unlike the Contact Information section which now shows the signed-in
    /// user's own username and email.
    private let supportEmail = "katsonsoftware@gmail.com"

    /// The full strength policy the backend enforces (Patterns.password): at
    /// least eight non-whitespace characters with a lower- and upper-case letter
    /// and a digit. Kept in sync with the website's change-password modal.
    private let strongPasswordRegex = "^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=\\S+$).{8,}$"

    // Kept so the appeals screen can be built with the same API/keychain.
    private let api: Networking
    private let keychainHelper: KeychainHelperProtocol

    init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        self.api = api
        self.keychainHelper = keychainHelper
        _viewModel = StateObject(wrappedValue: SettingsViewModel(api: api, keychainHelper: keychainHelper))
    }
    
    var body: some View {
        NavigationStack {
            List {
                // MARK: - Contact Information Section (issues #194/#197)
                // The signed-in user's own username + email (was a hardcoded
                // support address). Falls back to a placeholder while loading.
                Section(header: Text("Contact Information")) {
                    Text(viewModel.currentUsername ?? "…")
                        .foregroundColor(.gray)
                        .accessibilityIdentifier("ContactInfoUsername")
                    Text(viewModel.currentEmail ?? "…")
                        .foregroundColor(.gray)
                        .accessibilityIdentifier("ContactInfoEmail")
                }

                // MARK: - Contact Us Section (issue #194)
                // The support address, kept constant, for feedback and help.
                Section(header: Text("Contact Us")) {
                    Text(supportEmail)
                        .foregroundColor(.gray)
                        .accessibilityIdentifier("ContactUsEmail")
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

                // MARK: - Appeals Section
                Section {
                    NavigationLink {
                        AppealsView(api: api, keychainHelper: keychainHelper)
                    } label: {
                        Text("Hidden Content & Appeals")
                    }.accessibilityIdentifier("AppealsButton")
                }

                // MARK: - Blocked Users Section
                Section {
                    NavigationLink {
                        BlockedUsersView(api: api, keychainHelper: keychainHelper)
                    } label: {
                        Text("Blocked Users")
                    }.accessibilityIdentifier("BlockedUsersButton")
                }

                // MARK: - Security Section (issues #348 / #197)
                Section(header: Text("Security")) {
                    Button {
                        changePasswordCurrent = ""
                        changePasswordNew = ""
                        changePasswordConfirm = ""
                        viewModel.cancelPasswordChange()
                        showingChangePassword = true
                    } label: {
                        Text("Change Password")
                            .foregroundColor(.blue)
                    }.accessibilityIdentifier("ChangePasswordButton")

                    Button {
                        twoFactorConfirmCode = ""
                        twoFactorConfirmPassword = ""
                        viewModel.startTotpSetup()
                        showingEnrollTwoFactor = true
                    } label: {
                        Text("Enable Two-Factor Authentication")
                            .foregroundColor(.blue)
                    }.accessibilityIdentifier("EnableTwoFactorButton")

                    Button {
                        disablePassword = ""
                        disableCode = ""
                        disableUsesRecoveryCode = false
                        showingDisableTwoFactor = true
                    } label: {
                        Text("Disable Two-Factor Authentication")
                    }.accessibilityIdentifier("DisableTwoFactorButton")
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
            // Load the signed-in account's own username + email for the Contact
            // Information section (load-on-mount, matching the rest of the app).
            .onAppear {
                viewModel.loadCurrentUser()
            }
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
                Text(GVOAppConstants.privacyPolicyText)
            }
            .alert("Two-Factor Authentication", isPresented: $viewModel.showingTwoFactorStatusAlert) {
                Button("OK", role: .cancel) { }
            } message: {
                Text(viewModel.twoFactorStatusMessage)
            }
            .alert("Change Password", isPresented: $viewModel.showingPasswordChangeStatusAlert) {
                Button("OK", role: .cancel) { }
            } message: {
                Text(viewModel.passwordChangeStatusMessage)
            }
            .sheet(isPresented: $showingEnrollTwoFactor, onDismiss: {
                // A swipe-down (or the Done/Cancel buttons, which just close the
                // sheet) ends enrollment here. If recovery codes were already
                // issued the enrollment succeeded, so report it as enabled;
                // otherwise it was abandoned before confirming.
                if viewModel.recoveryCodes != nil {
                    viewModel.finishTotpEnrollment()
                } else {
                    viewModel.cancelTotpEnrollment()
                }
            }) {
                enrollTwoFactorSheet
                    // Block swipe-to-dismiss while a confirm is in flight (the
                    // request can succeed on the backend, and dismissing would
                    // drop the response along with the one-time recovery codes)
                    // and once those codes are on screen, since they're shown
                    // exactly once and can't be re-issued. The Cancel button is
                    // disabled for the same window; Done remains, since by then the
                    // codes are already on screen.
                    .interactiveDismissDisabled(
                        viewModel.isConfirmingTotp || viewModel.recoveryCodes != nil
                    )
            }
            .sheet(isPresented: $showingDisableTwoFactor) {
                disableTwoFactorSheet
            }
            .sheet(isPresented: $showingChangePassword, onDismiss: {
                // Clear the entered passwords from memory once the sheet closes —
                // they're sensitive and there's no reason to keep them around.
                // If the change went through, raise the confirmation alert;
                // otherwise it was cancelled, so just clear any inline error.
                changePasswordCurrent = ""
                changePasswordNew = ""
                changePasswordConfirm = ""
                if viewModel.passwordChangeSucceeded {
                    viewModel.finishPasswordChange()
                } else {
                    viewModel.cancelPasswordChange()
                }
            }) {
                changePasswordSheet
                    // A successful change closes the sheet automatically; the
                    // confirmation alert is then raised from onDismiss.
                    .onChange(of: viewModel.passwordChangeSucceeded) { _, succeeded in
                        if succeeded { showingChangePassword = false }
                    }
                    // Don't let a swipe-down drop an in-flight request; the
                    // backend may already have rotated the password.
                    .interactiveDismissDisabled(viewModel.isChangingPassword)
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

    // MARK: - Change Password Sheet (issue #197)

    /// Changing the password asks for the current one as well: the current
    /// password is required by the backend so a stolen session alone can't
    /// change it, and a successful change evicts the account's other sessions
    /// and remember-me cookies (only this device stays signed in).
    @ViewBuilder
    private var changePasswordSheet: some View {
        VStack(spacing: 16) {
            Text("Change Password")
                .font(.headline)
                .padding(.top)

            Text("Enter your current password and choose a new one. Your new password must be at least 8 characters and include an uppercase letter, a lowercase letter, and a number.")
                .font(.subheadline)
                .multilineTextAlignment(.center)

            if let changeError = viewModel.passwordChangeErrorMessage {
                Text(changeError)
                    .font(.subheadline)
                    .foregroundColor(.red)
                    .multilineTextAlignment(.center)
            }

            SecureField("Current password", text: $changePasswordCurrent)
                .padding().background(Color(.systemGray6)).cornerRadius(10)
                .textContentType(.password)
                .accessibilityIdentifier("ChangePasswordCurrentField")
            SecureField("New password", text: $changePasswordNew)
                .padding().background(Color(.systemGray6)).cornerRadius(10)
                .textContentType(.newPassword)
                .accessibilityIdentifier("ChangePasswordNewField")
            SecureField("Confirm new password", text: $changePasswordConfirm)
                .padding().background(Color(.systemGray6)).cornerRadius(10)
                .textContentType(.newPassword)
                .accessibilityIdentifier("ChangePasswordConfirmField")

            // Inline guidance so the disabled Change button isn't a dead end.
            if !changePasswordNew.isEmpty && !newPasswordIsStrong {
                Text("New password doesn't meet the requirements.")
                    .font(.footnote)
                    .foregroundColor(.red)
                    .multilineTextAlignment(.center)
            }
            if !changePasswordConfirm.isEmpty && changePasswordNew != changePasswordConfirm {
                Text("Passwords don't match.")
                    .font(.footnote)
                    .foregroundColor(.red)
            }
            if newPasswordIsStrong && changePasswordNew == changePasswordCurrent {
                Text("New password must be different from your current one.")
                    .font(.footnote)
                    .foregroundColor(.red)
                    .multilineTextAlignment(.center)
            }

            Button("Change Password") {
                viewModel.changePassword(currentPassword: changePasswordCurrent,
                                         newPassword: changePasswordNew)
            }
            .disabled(!changePasswordIsValid || viewModel.isChangingPassword)
            .padding()
            .background(Color.blue)
            .foregroundColor(.white)
            .cornerRadius(8)
            .accessibilityIdentifier("ConfirmChangePasswordButton")

            Button("Cancel") {
                showingChangePassword = false
            }
            .disabled(viewModel.isChangingPassword)
            .foregroundColor(.red)
        }
        .padding()
        .presentationDetents([.large])
    }

    /// Whether the new password satisfies the backend's strength policy.
    private var newPasswordIsStrong: Bool {
        changePasswordNew.range(of: strongPasswordRegex, options: .regularExpression) != nil
    }

    /// The client-side gate on the Change button: the new password must be
    /// strong, match its confirmation, and differ from the current one, and the
    /// current password must be present. The backend re-checks all of this.
    private var changePasswordIsValid: Bool {
        !changePasswordCurrent.isEmpty
            && newPasswordIsStrong
            && changePasswordNew == changePasswordConfirm
            && changePasswordNew != changePasswordCurrent
    }

    // MARK: - Two-Factor Sheets (issue #348)

    /// Enrollment: scan the QR (or copy the secret), confirm one code, then
    /// save the one-time recovery codes.
    @ViewBuilder
    private var enrollTwoFactorSheet: some View {
        VStack(spacing: 16) {
            Text("Enable Two-Factor Authentication")
                .font(.headline)
                .padding(.top)

            if let twoFactorError = viewModel.twoFactorErrorMessage {
                Text(twoFactorError)
                    .font(.subheadline)
                    .foregroundColor(.red)
                    .multilineTextAlignment(.center)
            }

            if let recoveryCodes = viewModel.recoveryCodes {
                Text("Two-factor authentication is on. Save these recovery codes somewhere safe — each works once, and they will not be shown again.")
                    .font(.subheadline)
                    .multilineTextAlignment(.center)
                ScrollView {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(recoveryCodes, id: \.self) { code in
                            Text(code)
                                .font(.system(.body, design: .monospaced))
                                .textSelection(.enabled)
                        }
                    }
                }
                .frame(maxHeight: 220)
                Button("Copy All") {
                    // Recovery codes are account keys, so keep them off other
                    // devices' clipboards (Universal Clipboard) and let them
                    // expire rather than sitting on the pasteboard indefinitely.
                    UIPasteboard.general.setItems(
                        [[UTType.plainText.identifier: recoveryCodes.joined(separator: "\n")]],
                        options: [
                            .localOnly: true,
                            .expirationDate: Date().addingTimeInterval(_recoveryCodeClipboardTTL),
                        ]
                    )
                }
                .accessibilityIdentifier("CopyRecoveryCodesButton")
                Button("Done") {
                    // Just close; onDismiss finishes enrollment (recovery codes
                    // are present), so the success path is handled in one place.
                    showingEnrollTwoFactor = false
                }
                .padding()
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(8)
                .accessibilityIdentifier("FinishTwoFactorEnrollmentButton")
            } else if let setup = viewModel.totpSetup {
                Text("Scan this QR code with your authenticator app (Google Authenticator, 1Password, …), or enter the secret manually.")
                    .font(.subheadline)
                    .multilineTextAlignment(.center)
                if let qrImage = Self.qrCodeImage(for: setup.otpauthUri) {
                    Image(uiImage: qrImage)
                        .interpolation(.none)
                        .resizable()
                        .scaledToFit()
                        .frame(width: 180, height: 180)
                        .background(Color.white)
                        .accessibilityLabel("Two-factor authentication QR code")
                        .accessibilityIdentifier("TwoFactorQRCode")
                }
                Text(setup.totpSecret)
                    .font(.system(.footnote, design: .monospaced))
                    .textSelection(.enabled)
                    .accessibilityIdentifier("TwoFactorSecretText")
                TextField("6-digit code", text: $twoFactorConfirmCode)
                    .padding().background(Color(.systemGray6)).cornerRadius(10)
                    .keyboardType(.numberPad)
                    .textContentType(.oneTimeCode)
                    .accessibilityIdentifier("TwoFactorConfirmCodeTextField")
                // Confirming asks for the account password as well: without it a
                // stolen session could enrol its own authenticator and lock the
                // real owner out permanently.
                SecureField("Account password", text: $twoFactorConfirmPassword)
                    .padding().background(Color(.systemGray6)).cornerRadius(10)
                    .textContentType(.password)
                    .accessibilityIdentifier("TwoFactorConfirmPasswordSecureField")
                Button("Verify") {
                    viewModel.confirmTotp(password: twoFactorConfirmPassword,
                                          code: twoFactorConfirmCode.trimmingCharacters(in: .whitespaces))
                }
                // Also blocked while a confirm is in flight: a second tap would
                // enqueue another enrollment whose response races the first, and
                // the loser reports a spurious "already enabled" failure.
                .disabled(viewModel.isConfirmingTotp
                          || twoFactorConfirmPassword.isEmpty
                          || !(twoFactorConfirmCode.trimmingCharacters(in: .whitespaces).count == 6
                               && twoFactorConfirmCode.trimmingCharacters(in: .whitespaces).allSatisfy(\.isNumber)))
                .padding()
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(8)
                .accessibilityIdentifier("ConfirmTwoFactorButton")
                Button("Cancel") {
                    showingEnrollTwoFactor = false
                }
                // Same reason swipe-dismiss is blocked mid-confirm: enrollment may
                // already have succeeded server-side, and tearing the sheet down
                // discards the response carrying the only copy of the recovery codes.
                .disabled(viewModel.isConfirmingTotp)
                .foregroundColor(.red)
            } else if viewModel.twoFactorErrorMessage != nil {
                // Setup failed before a secret arrived (the error is shown above);
                // offer a way out instead of an indefinite spinner.
                Button("Close") {
                    showingEnrollTwoFactor = false
                }
                .foregroundColor(.red)
            } else {
                ProgressView()
            }
        }
        .padding()
        .presentationDetents([.large])
    }

    /// Disabling requires the password plus a current or recovery code, so a
    /// stolen unlocked phone alone cannot strip the protection.
    @ViewBuilder
    private var disableTwoFactorSheet: some View {
        VStack(spacing: 16) {
            Text("Disable Two-Factor Authentication")
                .font(.headline)
                .padding(.top)

            Text("Confirm your password and a current \(disableUsesRecoveryCode ? "recovery" : "authenticator") code.")
                .font(.subheadline)
                .multilineTextAlignment(.center)

            SecureField("Password", text: $disablePassword)
                .padding().background(Color(.systemGray6)).cornerRadius(10)
                .accessibilityIdentifier("DisableTwoFactorPasswordField")
            TextField(disableUsesRecoveryCode ? "Recovery code" : "Authenticator code", text: $disableCode)
                .padding().background(Color(.systemGray6)).cornerRadius(10)
                .keyboardType(disableUsesRecoveryCode ? .asciiCapable : .numberPad)
                .autocapitalization(.none)
                .accessibilityIdentifier("DisableTwoFactorCodeField")
            Button(disableUsesRecoveryCode ? "Use an authenticator code instead" : "Use a recovery code instead") {
                disableUsesRecoveryCode.toggle()
                disableCode = ""
            }
            .accessibilityIdentifier("DisableToggleRecoveryCodeButton")

            Button("Disable") {
                showingDisableTwoFactor = false
                viewModel.disableTotp(
                    password: disablePassword,
                    code: disableCode.trimmingCharacters(in: .whitespaces),
                    isRecoveryCode: disableUsesRecoveryCode
                )
            }
            .disabled(disablePassword.isEmpty || !disableCodeIsValid)
            .padding()
            .background(Color.blue)
            .foregroundColor(.white)
            .cornerRadius(8)
            .accessibilityIdentifier("ConfirmDisableTwoFactorButton")

            Button("Cancel") {
                showingDisableTwoFactor = false
            }
            .foregroundColor(.red)
        }
        .padding()
        .presentationDetents([.medium])
    }

    /// Whether the disable-flow code is well-formed: a 6-digit authenticator
    /// code, or a 10-hex-character recovery code (backend Patterns), so clearly
    /// invalid codes can't be submitted.
    private var disableCodeIsValid: Bool {
        let trimmed = disableCode.trimmingCharacters(in: .whitespaces)
        if disableUsesRecoveryCode {
            return trimmed.count == 10 && trimmed.lowercased().allSatisfy { "0123456789abcdef".contains($0) }
        }
        return trimmed.count == 6 && trimmed.allSatisfy(\.isNumber)
    }

    /// A single reused CIContext: creating one is comparatively expensive, so
    /// keeping it static avoids churn each time the enrollment sheet recomputes.
    private static let ciContext = CIContext()

    /// Renders an otpauth:// URI as a QR code via CoreImage — no dependency.
    private static func qrCodeImage(for string: String) -> UIImage? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(string.utf8)
        guard let output = filter.outputImage?.transformed(by: CGAffineTransform(scaleX: 8, y: 8)),
              let cgImage = ciContext.createCGImage(output, from: output.extent) else {
            return nil
        }
        return UIImage(cgImage: cgImage)
    }
}

#Preview {
    // The preview needs the authManager in its environment to work correctly.
    SettingsView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper)
        .environmentObject(AuthenticationManager())
}
