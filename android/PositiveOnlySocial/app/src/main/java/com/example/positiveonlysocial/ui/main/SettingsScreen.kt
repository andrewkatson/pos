package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.DialogProperties
import com.example.positiveonlysocial.data.model.TotpSetupResponse
import com.google.zxing.BarcodeFormat
import com.google.zxing.qrcode.QRCodeWriter
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.auth.AuthenticationManager
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.data.security.KeychainHelper
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.SettingsViewModel
import com.example.positiveonlysocial.models.viewmodels.SettingsViewModelFactory
import com.example.positiveonlysocial.ui.navigation.Screen
import kotlinx.coroutines.launch
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme

@Composable
fun SettingsScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol,
    authenticationManager: AuthenticationManager
) {
    PositiveOnlySocialTheme {
        val viewModel: SettingsViewModel = viewModel(
            factory = SettingsViewModelFactory(api, authenticationManager, keychainHelper)
        )
        
        // We need AuthenticationManager to perform the actual logout/delete state update
        // Ideally this should be injected or passed.
        // Assuming we can get it from CompositionLocal or passed down.
        // For now, creating a new instance is WRONG because it won't share state.
        // It must be passed.
        // Updating MainScreen to pass it or using a singleton/DI.
        // Since I didn't pass it to MainScreen, I should probably fix that.
        // But wait, MainScreen doesn't take AuthManager.
        // Let's assume for now we can't easily get the shared instance without DI.
        // However, `AuthenticationManager` is designed to be a singleton.
        // If I use the one from `DependencyProvider` (if I added it there), it would work.
        // I didn't add it to DependencyProvider yet.
        // I will assume for this file that I can get it, or I'll add it to DependencyProvider in a separate step.
        // Let's use a placeholder for now and I'll fix DependencyProvider.
        
        // Temporary fix: We need to access the AuthManager used in Login/Register.
        // Since I don't have Hilt, I should have put it in DependencyProvider.
        // I will assume DependencyProvider.authManager exists.

        var showingLogoutConfirm by remember { mutableStateOf(false) }
        var showingDeleteConfirm by remember { mutableStateOf(false) }
        var showingVerifyIdentityDialog by remember { mutableStateOf(false) }
        var identityDateOfBirth by remember { mutableStateOf("") }
        var identityVerificationMessage by remember { mutableStateOf<String?>(null) }
        
        val scope = rememberCoroutineScope()
        val focusManager = LocalFocusManager.current
        // Local processing state for the dialog
        var isVerifying by remember { mutableStateOf(false) }
        
        // Observing ViewModel state
        val errorMessage by viewModel.errorMessage.collectAsState()
        val showingErrorAlert by viewModel.showingErrorAlert.collectAsState()

        var showingPrivacyPolicy by remember { mutableStateOf(false) }

        // Two-factor authentication dialogs (issue #348).
        var showingEnrollTwoFactor by remember { mutableStateOf(false) }
        var showingDisableTwoFactor by remember { mutableStateOf(false) }
        var twoFactorConfirmCode by remember { mutableStateOf("") }
        var twoFactorConfirmPassword by remember { mutableStateOf("") }
        var disablePassword by remember { mutableStateOf("") }
        var disableCode by remember { mutableStateOf("") }
        var disableUsesRecoveryCode by remember { mutableStateOf(false) }

        val totpSetup by viewModel.totpSetup.collectAsState()
        val recoveryCodes by viewModel.recoveryCodes.collectAsState()
        val isConfirmingTotp by viewModel.isConfirmingTotp.collectAsState()
        val twoFactorStatusMessage by viewModel.twoFactorStatusMessage.collectAsState()
        val clipboardManager = LocalClipboardManager.current

        // Change-password + contact info (issue #197/#194).
        var showingChangePassword by remember { mutableStateOf(false) }
        var changeCurrentPassword by remember { mutableStateOf("") }
        var changeNewPassword by remember { mutableStateOf("") }
        var changeConfirmPassword by remember { mutableStateOf("") }
        val isChangingPassword by viewModel.isChangingPassword.collectAsState()
        val passwordChangeMessage by viewModel.passwordChangeMessage.collectAsState()
        val currentUser by viewModel.currentUser.collectAsState()

        // Load the signed-in account's own username + email once, on mount.
        LaunchedEffect(Unit) { viewModel.loadCurrentUser() }

        // Once the change succeeds, close the dialog and wipe the entered
        // passwords — they're sensitive and must not linger in composition state.
        LaunchedEffect(passwordChangeMessage) {
            if (passwordChangeMessage != null && showingChangePassword) {
                showingChangePassword = false
                changeCurrentPassword = ""
                changeNewPassword = ""
                changeConfirmPassword = ""
            }
        }

        if (passwordChangeMessage != null) {
            AlertDialog(
                onDismissRequest = { viewModel.clearPasswordChangeMessage() },
                title = { Text("Change Password") },
                text = { Text(passwordChangeMessage!!) },
                confirmButton = {
                    Button(onClick = { viewModel.clearPasswordChangeMessage() }) {
                        Text("OK")
                    }
                }
            )
        }

        if (showingChangePassword) {
            // Cancelling clears the entered passwords too, so they don't linger
            // (or reappear if the dialog is reopened).
            val closeChangePasswordDialog = {
                showingChangePassword = false
                changeCurrentPassword = ""
                changeNewPassword = ""
                changeConfirmPassword = ""
            }
            ChangePasswordDialog(
                currentPassword = changeCurrentPassword,
                onCurrentPasswordChange = { changeCurrentPassword = it },
                newPassword = changeNewPassword,
                onNewPasswordChange = { changeNewPassword = it },
                confirmPassword = changeConfirmPassword,
                onConfirmPasswordChange = { changeConfirmPassword = it },
                isChanging = isChangingPassword,
                onChange = { viewModel.changePassword(changeCurrentPassword, changeNewPassword) },
                onCancel = closeChangePasswordDialog
            )
        }

        if (twoFactorStatusMessage != null) {
            AlertDialog(
                onDismissRequest = { viewModel.clearTwoFactorStatusMessage() },
                title = { Text("Two-Factor Authentication") },
                text = { Text(twoFactorStatusMessage!!) },
                confirmButton = {
                    Button(onClick = { viewModel.clearTwoFactorStatusMessage() }) {
                        Text("OK")
                    }
                }
            )
        }

        if (showingEnrollTwoFactor) {
            EnrollTwoFactorDialog(
                totpSetup = totpSetup,
                recoveryCodes = recoveryCodes,
                confirmCode = twoFactorConfirmCode,
                onConfirmCodeChange = { twoFactorConfirmCode = it },
                confirmPassword = twoFactorConfirmPassword,
                onConfirmPasswordChange = { twoFactorConfirmPassword = it },
                isConfirming = isConfirmingTotp,
                onVerify = { viewModel.confirmTotp(twoFactorConfirmPassword, twoFactorConfirmCode.trim()) },
                onCopySecret = { secret ->
                    clipboardManager.setText(AnnotatedString(secret))
                },
                onCopyRecoveryCodes = { codes ->
                    clipboardManager.setText(AnnotatedString(codes.joinToString("\n")))
                },
                onDone = {
                    showingEnrollTwoFactor = false
                    // Don't leave the account password sitting in composition state
                    // once the flow is over.
                    twoFactorConfirmCode = ""
                    twoFactorConfirmPassword = ""
                    viewModel.finishTotpEnrollment()
                },
                onCancel = {
                    showingEnrollTwoFactor = false
                    twoFactorConfirmCode = ""
                    twoFactorConfirmPassword = ""
                    viewModel.cancelTotpEnrollment()
                }
            )
        }

        if (showingDisableTwoFactor) {
            // Every exit path clears the password and code so the entered
            // secrets don't linger in composition state (or reappear if the
            // dialog is opened again).
            val closeDisableDialog = {
                showingDisableTwoFactor = false
                disablePassword = ""
                disableCode = ""
                disableUsesRecoveryCode = false
            }
            AlertDialog(
                onDismissRequest = closeDisableDialog,
                title = { Text("Disable Two-Factor Authentication") },
                text = {
                    Column {
                        Text(
                            "Confirm your password and a current " +
                                (if (disableUsesRecoveryCode) "recovery" else "authenticator") + " code."
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        TextField(
                            value = disablePassword,
                            onValueChange = { disablePassword = it },
                            label = { Text("Password") },
                            singleLine = true,
                            visualTransformation = PasswordVisualTransformation(),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                            modifier = Modifier.testTag("DisableTwoFactorPasswordField")
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        TextField(
                            value = disableCode,
                            onValueChange = { disableCode = it },
                            label = { Text(if (disableUsesRecoveryCode) "Recovery code" else "Authenticator code") },
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(
                                keyboardType = if (disableUsesRecoveryCode) KeyboardType.Ascii else KeyboardType.NumberPassword
                            ),
                            modifier = Modifier.testTag("DisableTwoFactorCodeField")
                        )
                        TextButton(onClick = {
                            disableUsesRecoveryCode = !disableUsesRecoveryCode
                            disableCode = ""
                        }) {
                            Text(
                                if (disableUsesRecoveryCode) "Use an authenticator code instead"
                                else "Use a recovery code instead"
                            )
                        }
                    }
                },
                confirmButton = {
                    Button(
                        onClick = {
                            // Hand the values to the request before clearing them.
                            val password = disablePassword
                            val code = disableCode.trim()
                            val isRecoveryCode = disableUsesRecoveryCode
                            closeDisableDialog()
                            viewModel.disableTotp(
                                password = password,
                                code = code,
                                isRecoveryCode = isRecoveryCode
                            )
                        },
                        enabled = disablePassword.isNotEmpty() && disableCode.isNotEmpty()
                    ) {
                        Text("Disable")
                    }
                },
                dismissButton = {
                    Button(onClick = closeDisableDialog) {
                        Text("Cancel")
                    }
                }
            )
        }

        if (showingPrivacyPolicy) {
            AlertDialog(
                onDismissRequest = { showingPrivacyPolicy = false },
                title = { Text("Privacy Policy") },
                text = {
                    Text(Constants.PRIVACY_POLICY_TEXT)
                },
                confirmButton = {
                    Button(onClick = { showingPrivacyPolicy = false }) {
                        Text("Ok")
                    }
                }
            )
        }

        if (showingLogoutConfirm) {
            AlertDialog(
                onDismissRequest = { showingLogoutConfirm = false },
                title = { Text("Are you sure you want to log out?") },
                confirmButton = {
                    Button(
                        onClick = {
                            showingLogoutConfirm = false
                            // Perform logout
                            // We need the auth manager here.
                            // viewModel.logout(authManager)
                            // Since I can't access authManager easily here without changing signature,
                            // I'll assume I can pass it or get it.
                            // Let's assume I'll update DependencyProvider to include it.
                            // val authManager = DependencyProvider.authManager
                            viewModel.logout()

                            // For now, just navigating to Login as a visual effect, 
                            // but logic needs AuthManager.
                            navController.navigate(Screen.Login.route) {
                                popUpTo(Screen.Home.route) { inclusive = true }
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = Color.Red)
                    ) {
                        Text("Confirm")
                    }
                },
                dismissButton = {
                    Button(onClick = { showingLogoutConfirm = false }) {
                        Text("Cancel")
                    }
                }
            )
        }

        if (showingDeleteConfirm) {
            AlertDialog(
                onDismissRequest = { showingDeleteConfirm = false },
                title = { Text("Delete Your Account?") },
                text = { Text("This action is permanent and cannot be undone.") },
                confirmButton = {
                    Button(
                        onClick = {
                            showingDeleteConfirm = false
                            viewModel.deleteAccount()
                            navController.navigate(Screen.Login.route) {
                                popUpTo(Screen.Home.route) { inclusive = true }
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = Color.Red)
                    ) {
                        Text("Delete")
                    }
                },
                dismissButton = {
                    Button(onClick = { showingDeleteConfirm = false }) {
                        Text("Cancel")
                    }
                }
            )
        }

        if (showingVerifyIdentityDialog) {
            AlertDialog(
                onDismissRequest = { showingVerifyIdentityDialog = false },
                title = { Text("Verify Identity") },
                modifier = Modifier.testTag("verifyIdentityDialog"),
                text = {
                    Column {
                        Text("Enter your Date of Birth:")
                        Spacer(modifier = Modifier.height(8.dp))
                        TextField(
                            value = identityDateOfBirth,
                            onValueChange = { identityDateOfBirth = it },
                            label = { Text("YYYY-MM-DD") },
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                            keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus() })
                        )
                         if (identityVerificationMessage != null) {
                             Spacer(modifier = Modifier.height(8.dp))
                             Text(identityVerificationMessage!!, color = MaterialTheme.colorScheme.primary)
                         }
                    }
                },
                confirmButton = {
                    Button(
                        onClick = {
                            scope.launch {
                                 isVerifying = true
                                 identityVerificationMessage = null
                                 try {
                                     val token = authenticationManager.session.value?.sessionToken ?: ""
                                     val response = api.verifyIdentity(
                                         token = token,
                                         request = com.example.positiveonlysocial.data.model.IdentityVerificationRequest(identityDateOfBirth)
                                     )
                                     if (response.isSuccessful) {
                                         identityVerificationMessage = "Identity verified successfully!"
                                        // Add a small delay so user can see the success message
                                        kotlinx.coroutines.delay(1500)
                                        // Dismiss the dialog
                                        showingVerifyIdentityDialog = false
                                        // Reset state
                                        identityDateOfBirth = ""
                                        identityVerificationMessage = null
                                     } else {
                                         identityVerificationMessage = "Verification failed."
                                     }
                                 } catch (e: Exception) {
                                     identityVerificationMessage = "Error: ${e.message}"
                                 } finally {
                                     isVerifying = false
                                 }
                            }
                        },
                        enabled = !isVerifying
                    ) {
                        if (isVerifying) {
                            CircularProgressIndicator(modifier = Modifier.size(16.dp))
                        } else {
                            Text("Verify")
                        }
                    }
                },
                dismissButton = {
                    Button(onClick = { showingVerifyIdentityDialog = false }) {
                        Text("Close")
                    }
                }
            )
        }

        if (showingErrorAlert) {
            AlertDialog(
                onDismissRequest = { viewModel.clearError() },
                title = { Text("Error") },
                text = { Text(errorMessage ?: "Unknown error") },
                confirmButton = {
                    Button(onClick = { viewModel.clearError() }) {
                        Text("OK")
                    }
                }
            )
        }

        Column(modifier = Modifier.fillMaxSize()) {
            Text(
                text = "Settings",
                style = MaterialTheme.typography.headlineMedium,
                modifier = Modifier.padding(16.dp)
            )
            
            ListListItem(text = "Verify Identity", textColor = Color.Blue) {
                showingVerifyIdentityDialog = true
            }
            
            HorizontalDivider()

            ListListItem(text = "Privacy Policy") {
                showingPrivacyPolicy = true
            }

            HorizontalDivider()

            ListListItem(text = "Hidden Content & Appeals") {
                navController.navigate(Screen.Appeals.route)
            }

            HorizontalDivider()

            ListListItem(text = "Blocked Users") {
                navController.navigate(Screen.BlockedUsers.route)
            }

            HorizontalDivider()

            Text(
                text = "Security",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(16.dp)
            )

            ListListItem(text = "Change Password", textColor = Color.Blue) {
                changeCurrentPassword = ""
                changeNewPassword = ""
                changeConfirmPassword = ""
                showingChangePassword = true
            }

            HorizontalDivider()

            ListListItem(text = "Enable Two-Factor Authentication", textColor = Color.Blue) {
                twoFactorConfirmCode = ""
                twoFactorConfirmPassword = ""
                viewModel.startTotpSetup()
                showingEnrollTwoFactor = true
            }

            HorizontalDivider()

            ListListItem(text = "Disable Two-Factor Authentication") {
                disablePassword = ""
                disableCode = ""
                disableUsesRecoveryCode = false
                showingDisableTwoFactor = true
            }

            HorizontalDivider()

            ListListItem(text = "Logout", textColor = Color.Red) {
                showingLogoutConfirm = true
            }
            
            HorizontalDivider()
            
            Text(
                text = "Contact Information",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(16.dp)
            )

            // The signed-in user's own username + email (issue #197/#194). Shows
            // a placeholder until loadCurrentUser() resolves. Read-only rows, so
            // they aren't rendered as clickable no-op tap targets.
            StaticListItem(text = currentUser?.username ?: "…")

            HorizontalDivider()

            StaticListItem(text = currentUser?.email ?: "…")

            HorizontalDivider()

            Text(
                text = "Contact Us",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(16.dp)
            )

            // Support address for feedback/help — a constant, not the user's own
            // email (issue #194). Read-only, like the contact-info rows above.
            StaticListItem(text = Constants.SUPPORT_EMAIL)

            HorizontalDivider()

            Text(
                text = "Account Actions",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(16.dp)
            )
            
            ListListItem(text = "Delete Account", textColor = Color.Red) {
                showingDeleteConfirm = true
            }
        }
    }
}

/**
 * Enrollment dialog (issue #348): scan the QR (or copy the secret), confirm one
 * code, then save the one-time recovery codes. Which step is shown is driven by
 * the view model state — `recoveryCodes` non-null means confirmed.
 */
@Composable
private fun EnrollTwoFactorDialog(
    totpSetup: TotpSetupResponse?,
    recoveryCodes: List<String>?,
    confirmCode: String,
    onConfirmCodeChange: (String) -> Unit,
    confirmPassword: String,
    onConfirmPasswordChange: (String) -> Unit,
    isConfirming: Boolean,
    onVerify: () -> Unit,
    onCopySecret: (String) -> Unit,
    onCopyRecoveryCodes: (List<String>) -> Unit,
    onDone: () -> Unit,
    onCancel: () -> Unit
) {
    val isConfirmCodeValid = confirmCode.trim().length == 6 && confirmCode.trim().all { it.isDigit() }
    // The password is required too: without it a stolen session could enrol its
    // own authenticator and lock the real owner out permanently.
    // Also blocked while a confirm is in flight: a second tap would enqueue
    // another enrollment, and a later failure ("already enabled") would raise an
    // error alert over the recovery codes the first one just produced.
    // isNotBlank, not isNotEmpty: a whitespace-only password can never be valid
    // (the backend password pattern forbids whitespace), so it must not enable
    // Verify. The password is sent verbatim otherwise — login and the disable
    // dialog don't trim either, and trimming only here would let enrollment
    // accept a password the subsequent login would reject.
    val canConfirm = isConfirmCodeValid && confirmPassword.isNotBlank() && !isConfirming

    AlertDialog(
        // Recovery codes are shown exactly once and the backend can't re-issue
        // them, so on that step the dialog can't be dismissed by a back press or
        // a tap outside — the user has to choose Copy All / Done deliberately.
        // It's also sealed while a confirm is in flight: enrollment may already
        // have succeeded, and dismissing would drop the response carrying the
        // only copy of the codes. Otherwise dismissing abandons a pending setup.
        properties = DialogProperties(
            dismissOnBackPress = recoveryCodes == null && !isConfirming,
            dismissOnClickOutside = recoveryCodes == null && !isConfirming,
        ),
        // Defensive: if a dismissal ever does get through on the codes step, 2FA
        // is already enabled server-side, so report it rather than cancelling.
        onDismissRequest = { if (recoveryCodes != null) onDone() else onCancel() },
        title = { Text("Enable Two-Factor Authentication") },
        text = {
            Column(
                modifier = Modifier.verticalScroll(rememberScrollState()),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                when {
                    recoveryCodes != null -> {
                        Text(
                            "Two-factor authentication is on. Save these recovery codes somewhere " +
                                "safe — each works once, and they will not be shown again."
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        // Tag the list container once and index each row, so a
                        // UI test can select a single node unambiguously.
                        recoveryCodes.forEachIndexed { index, code ->
                            Text(code, fontFamily = FontFamily.Monospace, modifier = Modifier.testTag("RecoveryCode_$index"))
                        }
                    }
                    totpSetup != null -> {
                        Text(
                            "Scan this QR code with your authenticator app (Google Authenticator, " +
                                "1Password, …), or enter the secret manually."
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        val qrBitmap = remember(totpSetup.otpauthUri) { qrCodeBitmap(totpSetup.otpauthUri) }
                        if (qrBitmap != null) {
                            Image(
                                bitmap = qrBitmap.asImageBitmap(),
                                contentDescription = "Two-factor QR code",
                                modifier = Modifier.size(200.dp).testTag("TwoFactorQRCode")
                            )
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                totpSetup.totpSecret,
                                fontFamily = FontFamily.Monospace,
                                modifier = Modifier.testTag("TwoFactorSecret")
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            TextButton(
                                onClick = { onCopySecret(totpSetup.totpSecret) },
                                modifier = Modifier.testTag("CopySecretButton")
                            ) {
                                Text("Copy")
                            }
                        }
                        Spacer(modifier = Modifier.height(12.dp))
                        TextField(
                            value = confirmCode,
                            onValueChange = onConfirmCodeChange,
                            label = { Text("6-digit code") },
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                            modifier = Modifier.testTag("TwoFactorConfirmCodeField")
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        TextField(
                            value = confirmPassword,
                            onValueChange = onConfirmPasswordChange,
                            label = { Text("Account password") },
                            singleLine = true,
                            visualTransformation = PasswordVisualTransformation(),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                            modifier = Modifier.testTag("TwoFactorConfirmPasswordField")
                        )
                    }
                    else -> {
                        CircularProgressIndicator()
                    }
                }
            }
        },
        confirmButton = {
            when {
                recoveryCodes != null -> {
                    Row {
                        Button(onClick = { onCopyRecoveryCodes(recoveryCodes) }) {
                            Text("Copy All")
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        Button(onClick = onDone, modifier = Modifier.testTag("FinishTwoFactorButton")) {
                            Text("Done")
                        }
                    }
                }
                totpSetup != null -> {
                    Button(onClick = onVerify, enabled = canConfirm, modifier = Modifier.testTag("ConfirmTwoFactorButton")) {
                        Text("Verify")
                    }
                }
            }
        },
        dismissButton = {
            if (recoveryCodes == null) {
                // Disabled mid-confirm for the same reason the dialog can't be
                // dismissed then: enrollment may already have succeeded, and
                // tearing the dialog down discards the response carrying the only
                // copy of the recovery codes.
                Button(onClick = onCancel, enabled = !isConfirming) { Text("Cancel") }
            }
        }
    )
}

/**
 * Change-password dialog (issue #197). Three password fields with client-side
 * validation mirroring the backend's registration strength policy; the current
 * password is required as well as the session so a stolen session alone can't
 * change it. Passwords are cleared from composition state on every exit path by
 * the caller.
 */
@Composable
private fun ChangePasswordDialog(
    currentPassword: String,
    onCurrentPasswordChange: (String) -> Unit,
    newPassword: String,
    onNewPasswordChange: (String) -> Unit,
    confirmPassword: String,
    onConfirmPasswordChange: (String) -> Unit,
    isChanging: Boolean,
    onChange: () -> Unit,
    onCancel: () -> Unit
) {
    // The full strength policy the backend enforces at registration (see
    // Patterns.password in backend/user_system/constants.py): at least eight
    // non-whitespace characters with a lower- and upper-case letter and a digit.
    val strongPassword = remember { Regex("^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=\\S+$).{8,}$") }
    val isNewStrong = strongPassword.matches(newPassword)
    val doPasswordsMatch = newPassword == confirmPassword
    val isNewDifferent = newPassword != currentPassword
    // Blocked while a change is in flight, mirroring the 2FA dialogs: a second
    // tap would enqueue another request before the first settles.
    val canSubmit = currentPassword.isNotEmpty() && isNewStrong &&
        doPasswordsMatch && isNewDifferent && !isChanging

    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text("Change Password") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                Text(
                    "Enter your current password and choose a new one. Your new password must " +
                        "be at least 8 characters and include an uppercase letter, a lowercase " +
                        "letter, and a number."
                )
                Spacer(modifier = Modifier.height(8.dp))
                TextField(
                    value = currentPassword,
                    onValueChange = onCurrentPasswordChange,
                    label = { Text("Current password") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    modifier = Modifier.testTag("ChangePasswordCurrentField")
                )
                Spacer(modifier = Modifier.height(8.dp))
                TextField(
                    value = newPassword,
                    onValueChange = onNewPasswordChange,
                    label = { Text("New password") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    modifier = Modifier.testTag("ChangePasswordNewField")
                )
                Spacer(modifier = Modifier.height(8.dp))
                TextField(
                    value = confirmPassword,
                    onValueChange = onConfirmPasswordChange,
                    label = { Text("Confirm new password") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    modifier = Modifier.testTag("ChangePasswordConfirmField")
                )
                // Inline guidance so the disabled Change button isn't a dead end.
                if (newPassword.isNotEmpty() && !isNewStrong) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        "New password doesn't meet the requirements.",
                        color = MaterialTheme.colorScheme.error
                    )
                }
                if (confirmPassword.isNotEmpty() && !doPasswordsMatch) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("Passwords don't match.", color = MaterialTheme.colorScheme.error)
                }
                if (isNewStrong && !isNewDifferent) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        "New password must be different from your current one.",
                        color = MaterialTheme.colorScheme.error
                    )
                }
            }
        },
        confirmButton = {
            Button(
                onClick = onChange,
                enabled = canSubmit,
                modifier = Modifier.testTag("ConfirmChangePasswordButton")
            ) {
                Text("Change Password")
            }
        },
        dismissButton = {
            Button(onClick = onCancel, enabled = !isChanging) {
                Text("Cancel")
            }
        }
    )
}

/** Renders an otpauth:// URI as a QR bitmap via ZXing — no network, no view service. */
private fun qrCodeBitmap(content: String, size: Int = 512): android.graphics.Bitmap? {
    return try {
        val bitMatrix = QRCodeWriter().encode(content, BarcodeFormat.QR_CODE, size, size)
        // Fill an IntArray and blit it in one setPixels() call rather than
        // ~260k individual setPixel() calls, which is far cheaper on the caller.
        val pixels = IntArray(size * size)
        for (y in 0 until size) {
            val rowStart = y * size
            for (x in 0 until size) {
                pixels[rowStart + x] =
                    if (bitMatrix.get(x, y)) android.graphics.Color.BLACK else android.graphics.Color.WHITE
            }
        }
        android.graphics.Bitmap.createBitmap(size, size, android.graphics.Bitmap.Config.RGB_565).apply {
            setPixels(pixels, 0, size, 0, 0, size, size)
        }
    } catch (e: Exception) {
        null
    }
}

@Composable
fun ListListItem(text: String, textColor: Color = Color.Unspecified, onClick: () -> Unit) {
    Surface(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth()
    ) {
        Text(
            text = text,
            color = textColor,
            modifier = Modifier.padding(16.dp)
        )
    }
}

/**
 * A read-only settings row: same padding/typography as [ListListItem] but with
 * no clickable surface, so informational rows (the account's own contact details
 * and the support address) aren't misleading no-op tap targets.
 */
@Composable
fun StaticListItem(text: String, textColor: Color = Color.Unspecified) {
    Text(
        text = text,
        color = textColor,
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp)
    )
}

@Preview(showBackground = true)
@Composable
fun SettingsScreenPreview() {
    SettingsScreen(
        navController = rememberNavController(),
        api = PreviewHelpers.mockApi,
        keychainHelper = PreviewHelpers.mockKeychainHelper,
        authenticationManager = PreviewHelpers.mockAuthManager
    )
}
