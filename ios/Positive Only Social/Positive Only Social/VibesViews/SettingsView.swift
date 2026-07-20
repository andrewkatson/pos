//
//  SettingsView.swift
//  Positive Only Social
//
//  Created by Andrew Katson on 10/8/25.
//

import SwiftUI
import CoreImage.CIFilterBuiltins

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
    @State private var disablePassword = ""
    @State private var disableCode = ""
    @State private var disableUsesRecoveryCode = false

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

                // MARK: - Appeals Section
                Section {
                    NavigationLink {
                        AppealsView(api: api, keychainHelper: keychainHelper)
                    } label: {
                        Text("Hidden Content & Appeals")
                    }.accessibilityIdentifier("AppealsButton")
                }

                // MARK: - Security Section (issue #348)
                Section(header: Text("Security")) {
                    Button {
                        twoFactorConfirmCode = ""
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
            }
            .sheet(isPresented: $showingDisableTwoFactor) {
                disableTwoFactorSheet
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
                    UIPasteboard.general.string = recoveryCodes.joined(separator: "\n")
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
                Button("Verify") {
                    viewModel.confirmTotp(code: twoFactorConfirmCode.trimmingCharacters(in: .whitespaces))
                }
                .disabled(!(twoFactorConfirmCode.trimmingCharacters(in: .whitespaces).count == 6
                            && twoFactorConfirmCode.trimmingCharacters(in: .whitespaces).allSatisfy(\.isNumber)))
                .padding()
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(8)
                .accessibilityIdentifier("ConfirmTwoFactorButton")
                Button("Cancel") {
                    showingEnrollTwoFactor = false
                }
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
