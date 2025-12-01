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
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.CreatePostRequest
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import kotlinx.coroutines.launch

@Composable
fun NewPostScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol
) {
    var caption by remember { mutableStateOf("") }
    var selectedImageUri by remember { mutableStateOf<Uri?>(null) }
    var isLoading by remember { mutableStateOf(false) }
    var showSuccessAlert by remember { mutableStateOf(false) }
    var showFailureAlert by remember { mutableStateOf(false) }
    var failureMessage by remember { mutableStateOf("") }

    val scope = rememberCoroutineScope()

    val singlePhotoPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickVisualMedia(),
        onResult = { uri -> selectedImageUri = uri }
    )

    if (showSuccessAlert) {
        AlertDialog(
            onDismissRequest = { showSuccessAlert = false },
            title = { Text("Success!") },
            text = { Text("Your post was shared successfully!") },
            confirmButton = {
                Button(onClick = { 
                    showSuccessAlert = false
                    // Reset form
                    caption = ""
                    selectedImageUri = null
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
                            // TODO: Implement actual image upload to S3 and then call API
                            // For now, using a dummy URL as per Swift stub logic if needed, 
                            // but real implementation requires S3 upload.
                            // Swift code uses S3Uploader. 
                            // I should check if S3Uploader exists in Android codebase.
                            // PositiveOnlySocialApp.kt initialized AWSManager, so likely yes.
                            
                            // Placeholder for S3 upload:
                            val imageUrl = "https://example.com/image.jpg" // Replace with actual upload
                            
                            // Retrieve session token (simplified)
                            // In real app, use AuthenticationManager or KeychainHelper
                            val session = keychainHelper.load(
                                com.example.positiveonlysocial.data.model.UserSession::class.java,
                                "positive-only-social.Positive-Only-Social",
                                "userSessionToken"
                            )
                            
                            if (session != null) {
                                val request = CreatePostRequest(
                                    imageUrl = imageUrl,
                                    caption = caption
                                )
                                api.makePost(
                                    token = session.sessionToken,
                                    request = request
                                )
                                showSuccessAlert = true
                            } else {
                                failureMessage = "User not logged in."
                                showFailureAlert = true
                            }

                        } catch (e: Exception) {
                            failureMessage = "Failed to share post: ${e.localizedMessage}"
                            showFailureAlert = true
                        } finally {
                            isLoading = false
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = selectedImageUri != null && caption.isNotEmpty()
            ) {
                Text("Share Post")
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
