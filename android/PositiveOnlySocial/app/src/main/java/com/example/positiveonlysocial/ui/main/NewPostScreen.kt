package com.example.positiveonlysocial.ui.main

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import coil.compose.AsyncImage
import androidx.compose.ui.platform.LocalContext
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.constants.Constants
import com.example.positiveonlysocial.data.model.CreatePostRequest
import com.example.positiveonlysocial.ui.components.CharacterCounter
import com.example.positiveonlysocial.ui.components.isWithinLength
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.data.uploader.S3Uploader
import java.util.UUID
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.dismissKeyboardOnTap
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import kotlinx.coroutines.launch
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme

@Composable
fun NewPostScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol
) {
    PositiveOnlySocialTheme {
        var caption by remember { mutableStateOf("") }
        var selectedImageUri by remember { mutableStateOf<Uri?>(null) }
        var isLoading by remember { mutableStateOf(false) }
        var showSuccessAlert by remember { mutableStateOf(false) }
        var successMessage by remember { mutableStateOf("Your post was shared successfully!") }
        var showFailureAlert by remember { mutableStateOf(false) }
        var failureMessage by remember { mutableStateOf("") }

        val scope = rememberCoroutineScope()
        val context = LocalContext.current

        val singlePhotoPickerLauncher = rememberLauncherForActivityResult(
            contract = ActivityResultContracts.PickVisualMedia(),
            onResult = { uri -> selectedImageUri = uri }
        )

        if (showSuccessAlert) {
            AlertDialog(
                onDismissRequest = { showSuccessAlert = false },
                title = { Text("Success!") },
                text = { Text(successMessage) },
                confirmButton = {
                    Button(onClick = { 
                        showSuccessAlert = false
                        // Reset form
                        caption = ""
                        selectedImageUri = null
                        // Navigate back to Home tab
                        navController.navigate(com.example.positiveonlysocial.ui.navigation.Screen.Home.route) {
                            popUpTo(com.example.positiveonlysocial.ui.navigation.Screen.Home.route) { inclusive = true }
                        }
                    }) {
                        Text("OK")
                    }
                }
            )
        }

        if (showFailureAlert) {
            AlertDialog(
                onDismissRequest = { showFailureAlert = false },
                title = { Text("Post Failed") },
                text = { Text(failureMessage) },
                confirmButton = {
                    Button(onClick = { showFailureAlert = false }) {
                        Text("OK")
                    }
                }
            )
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .dismissKeyboardOnTap()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Text(
                text = "Create Post",
                style = MaterialTheme.typography.headlineMedium
            )

            Button(
                onClick = {
                    singlePhotoPickerLauncher.launch(
                        PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)
                    )
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Select a photo")
            }

            if (selectedImageUri != null) {
                AsyncImage(
                    model = selectedImageUri,
                    contentDescription = "Selected Image",
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(200.dp),
                    contentScale = ContentScale.Crop
                )
            }

            TextField(
                value = caption,
                onValueChange = { caption = it },
                label = { Text("Caption") },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(100.dp)
            )

            CharacterCounter(text = caption, max = Constants.MAX_CAPTION_LENGTH)

            Spacer(modifier = Modifier.weight(1f))

            if (isLoading) {
                Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            } else {
                Button(
                    onClick = {
                        scope.launch {
                            isLoading = true
                            try {
                                val uri = selectedImageUri ?: return@launch
                                val inputStream = context.contentResolver.openInputStream(uri)
                                val bytes = inputStream?.use { it.readBytes() }
                                
                                if (bytes == null) {
                                    failureMessage = "Failed to read image data."
                                    showFailureAlert = true
                                    return@launch
                                }

                                // Load session first so we can scope the S3 key to the authenticated user.
                                val session = keychainHelper.load(
                                    com.example.positiveonlysocial.data.model.UserSession::class.java,
                                    "positive-only-social.Positive-Only-Social",
                                    "userSessionToken"
                                )

                                if (session == null) {
                                    failureMessage = "User not logged in."
                                    showFailureAlert = true
                                    return@launch
                                }

                                if (session.userId.isEmpty()) {
                                    failureMessage = "Session is invalid. Please log in again."
                                    showFailureAlert = true
                                    return@launch
                                }

                                val fileName = "${session.userId}/${UUID.randomUUID()}.jpg"
                                val s3Uploader = S3Uploader()

                                val uploadUrl = s3Uploader.upload(bytes, fileName)

                                val request = CreatePostRequest(
                                    imageUrl = uploadUrl.toString(),
                                    caption = caption
                                )
                                val response = api.makePost(
                                    token = session.sessionToken,
                                    request = request
                                )
                                if (!response.isSuccessful) {
                                    // A non-2xx (e.g. final classifier rejection)
                                    // must not show a success dialog.
                                    val raw = response.errorBody()?.string()
                                    failureMessage = "Failed to share post: ${raw ?: "Please try again."}"
                                    showFailureAlert = true
                                    return@launch
                                }
                                // A post flagged by automated review is created
                                // hidden pending appeal; say so rather than
                                // implying it went live.
                                val body = response.body()
                                successMessage = if (body?.hidden == true) {
                                    body.message
                                        ?: "Your post did not pass automated review. It is hidden for now but you can appeal the decision."
                                } else {
                                    "Your post was shared successfully!"
                                }
                                showSuccessAlert = true

                            } catch (e: Exception) {
                                failureMessage = "Failed to share post: ${e.localizedMessage}"
                                showFailureAlert = true
                            } finally {
                                isLoading = false
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = selectedImageUri != null && caption.isNotEmpty() && isWithinLength(caption, Constants.MAX_CAPTION_LENGTH)
                ) {
                    Text("Share Post")
                }
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun NewPostScreenPreview() {
    NewPostScreen(
        navController = rememberNavController(),
        api = PreviewHelpers.mockApi,
        keychainHelper = PreviewHelpers.mockKeychainHelper
    )
}
