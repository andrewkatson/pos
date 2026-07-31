package com.example.positiveonlysocial.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.NavController
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.api.ApiErrors
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.data.model.RegisterRequest
import com.example.positiveonlysocial.data.model.InterestOption
import com.example.positiveonlysocial.data.model.InterestVocabulary
import com.example.positiveonlysocial.ui.components.InterestPicker
import com.example.positiveonlysocial.ui.dismissKeyboardOnTap
import com.example.positiveonlysocial.ui.navigation.Screen
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme
import kotlinx.coroutines.launch

@Composable
fun RegisterScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI
) {
    PositiveOnlySocialTheme {
        var username by remember { mutableStateOf("") }
        var email by remember { mutableStateOf("") }
        var password by remember { mutableStateOf("") }
        var confirmPassword by remember { mutableStateOf("") }
        var dateOfBirth by remember { mutableStateOf("") }
        var isLoading by remember { mutableStateOf(false) }
        var errorMessage by remember { mutableStateOf<String?>(null) }
        var showingErrorAlert by remember { mutableStateOf(false) }
        var showingPrivacyPolicy by remember { mutableStateOf(false) }

        // Optional positive interests collected during sign-up (issues #446/#35),
        // sent along in the register call since the account has no session yet.
        var interestOptions by remember { mutableStateOf<List<InterestOption>>(emptyList()) }
        var selectedInterestSlugs by remember { mutableStateOf<List<String>>(emptyList()) }
        var freeformInterests by remember { mutableStateOf<List<String>>(emptyList()) }

        val scope = rememberCoroutineScope()
        val focusManager = LocalFocusManager.current

        // Load the preset bucket vocabulary (public endpoint). Best-effort: on
        // failure the picker shows no presets and freeform entry still works.
        LaunchedEffect(Unit) {
            try {
                val response = api.getInterestOptions()
                if (response.isSuccessful) {
                    interestOptions = response.body()?.options.orEmpty()
                }
            } catch (_: Exception) {
                // Interests are optional at sign-up.
            }
        }

        val usernameRequirements = AuthRequirements.username(username)
        val passwordRequirements = AuthRequirements.password(password)
        val isPasswordMatching = confirmPassword.isEmpty() || password == confirmPassword
        val isFormValid = AuthRequirements.allMet(usernameRequirements) &&
            email.isNotEmpty() &&
            AuthRequirements.allMet(passwordRequirements) &&
            password == confirmPassword &&
            dateOfBirth.isNotEmpty()

        if (showingPrivacyPolicy) {
            AlertDialog(
                onDismissRequest = { showingPrivacyPolicy = false },
                title = { Text("Privacy Policy") },
                text = {
                    Text(Constants.PRIVACY_POLICY_TEXT)
                },
                confirmButton = {
                    Button(onClick = { 
                        showingPrivacyPolicy = false
                        // Start registration
                        isLoading = true
                        scope.launch {
                            try {
                                val registerRequest = RegisterRequest(
                                    username = username,
                                    email = email,
                                    password = password,
                                    rememberMe = "false",
                                    ip = "127.0.0.1",
                                    dateOfBirth = dateOfBirth,
                                    interestCategories = selectedInterestSlugs.ifEmpty { null },
                                    interestFreeform = freeformInterests.ifEmpty { null }
                                )

                                val response = api.register(
                                    request = registerRequest
                                )

                                if (response.isSuccessful) {
                                    // The account can't do anything until the emailed
                                    // verification link is used (issue #237), so don't
                                    // keep the registration session — park the user on
                                    // the "check your email" screen (which welcomes the
                                    // new member with their join number, issue #198) and
                                    // have them log in after verifying.
                                    val membershipNumber = response.body()?.membershipNumber
                                    navController.navigate(Screen.CheckEmail.createRoute(email, membershipNumber)) {
                                        popUpTo(Screen.Welcome.route)
                                    }
                                } else {
                                    val errorMsg = ApiErrors.messageFor(response, fallback = "Registration failed. Username or email may be taken.")
                                    errorMessage = errorMsg
                                    showingErrorAlert = true
                                }
                            } catch (e: Exception) {
                                errorMessage = "Registration failed. Please check your network connection."
                                showingErrorAlert = true
                            } finally {
                                isLoading = false
                            }
                        }
                    }) {
                        Text("Ok")
                    }
                },
                dismissButton = {
                    Button(onClick = { showingPrivacyPolicy = false }) {
                        Text("Cancel")
                    }
                }
            )
        }

        if (showingErrorAlert) {
            AlertDialog(
                onDismissRequest = { showingErrorAlert = false },
                title = { Text("Registration Failed") },
                text = { Text(errorMessage ?: "An unknown error occurred.") },
                confirmButton = {
                    Button(onClick = { showingErrorAlert = false }) {
                        Text("OK")
                    }
                }
            )
        }

        // Keep the Register button pinned below a scrollable field area so it
        // stays reachable when the keyboard covers the lower fields (#277). The
        // inner column scrolls (bounded by the outer column's weight), so the
        // button never gets pushed off-screen.
        Column(
            modifier = Modifier
                .fillMaxSize()
                .dismissKeyboardOnTap()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Column(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(15.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
            Text(
                text = "Create Account",
                fontSize = 30.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(bottom = 20.dp)
            )

            TextField(
                value = username,
                onValueChange = { username = it },
                label = { Text("Username") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus() })
            )

            if (username.isNotEmpty()) {
                RequirementHints(usernameRequirements)
            }

            TextField(
                value = email,
                onValueChange = { email = it },
                label = { Text("Email") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus() })
            )

            TextField(
                value = dateOfBirth,
                onValueChange = { dateOfBirth = it },
                label = { Text("Date of Birth (YYYY-MM-DD)") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus() })
            )

            TextField(
                value = password,
                onValueChange = { password = it },
                label = { Text("Password") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus() })
            )

            if (password.isNotEmpty()) {
                RequirementHints(passwordRequirements)
            }

            TextField(
                value = confirmPassword,
                onValueChange = { confirmPassword = it },
                label = { Text("Confirm Password") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus() })
            )

            if (!isPasswordMatching) {
                Text(
                    text = "Passwords do not match.",
                    color = Color.Red,
                    fontSize = 12.sp,
                    modifier = Modifier.fillMaxWidth()
                )
            }

            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "Interests (optional)",
                fontWeight = FontWeight.Bold,
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(modifier = Modifier.height(8.dp))
            InterestPicker(
                options = interestOptions,
                selectedSlugs = selectedInterestSlugs,
                freeformTerms = freeformInterests,
                rejected = emptyList(),
                isBusy = isLoading,
                onToggle = { slug ->
                    selectedInterestSlugs =
                        if (selectedInterestSlugs.contains(slug)) selectedInterestSlugs - slug
                        else selectedInterestSlugs + slug
                },
                onAddFreeform = { terms ->
                    val seen = freeformInterests.map { it.lowercase() }.toMutableSet()
                    val next = freeformInterests.toMutableList()
                    for (term in terms) {
                        val key = term.lowercase()
                        if (!seen.contains(key) && next.size < InterestVocabulary.MAX_FREEFORM_INTERESTS) {
                            seen.add(key)
                            next.add(term)
                        }
                    }
                    freeformInterests = next
                },
                onRemoveFreeform = { term -> freeformInterests = freeformInterests.filter { it != term } }
            )

            }

            Spacer(modifier = Modifier.height(16.dp))

            if (isLoading) {
                CircularProgressIndicator()
            } else {
                Button(
                    onClick = {
                        showingPrivacyPolicy = true
                    },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = isFormValid
                ) {
                    Text("Register", fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun RegisterScreenPreview() {
    RegisterScreen(
        navController = rememberNavController(),
        api = PreviewHelpers.mockApi
    )
}
