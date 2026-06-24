package com.example.positiveonlysocial.ui.main

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import androidx.navigation.compose.rememberNavController
import com.example.positiveonlysocial.api.PositiveOnlySocialAPI
import com.example.positiveonlysocial.data.model.MyAppeal
import com.example.positiveonlysocial.data.security.KeychainHelperProtocol
import com.example.positiveonlysocial.models.viewmodels.AppealsViewModel
import com.example.positiveonlysocial.models.viewmodels.AppealsViewModelFactory
import com.example.positiveonlysocial.ui.preview.PreviewHelpers
import com.example.positiveonlysocial.ui.theme.PositiveOnlySocialTheme

private fun hiddenReasonLabel(reason: String): String = when (reason) {
    "classifier" -> "Flagged by automated review"
    "reports" -> "Hidden after user reports"
    else -> "Hidden"
}

/** The item being appealed (drives the reason dialog). */
private data class AppealTarget(val type: String, val id: String, val preview: String)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppealsScreen(
    navController: NavController,
    api: PositiveOnlySocialAPI,
    keychainHelper: KeychainHelperProtocol
) {
    PositiveOnlySocialTheme {
        val viewModel: AppealsViewModel = viewModel(
            factory = AppealsViewModelFactory(api, keychainHelper)
        )

        val hiddenPosts by viewModel.hiddenPosts.collectAsState()
        val hiddenComments by viewModel.hiddenComments.collectAsState()
        val appeals by viewModel.appeals.collectAsState()
        val errorMessage by viewModel.errorMessage.collectAsState()

        var target by remember { mutableStateOf<AppealTarget?>(null) }
        var reasonText by remember { mutableStateOf("") }

        LaunchedEffect(Unit) { viewModel.load() }

        if (errorMessage != null) {
            AlertDialog(
                onDismissRequest = { viewModel.clearError() },
                title = { Text("Error") },
                text = { Text(errorMessage ?: "Unknown error") },
                confirmButton = { Button(onClick = { viewModel.clearError() }) { Text("OK") } }
            )
        }

        target?.let { t ->
            AlertDialog(
                onDismissRequest = { target = null; reasonText = "" },
                title = { Text("Appeal this ${t.type}") },
                text = {
                    Column {
                        Text(t.preview, style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                        Spacer(Modifier.height(8.dp))
                        TextField(
                            value = reasonText,
                            onValueChange = { reasonText = it },
                            label = { Text("Why should this be restored?") },
                            modifier = Modifier.testTag("appealReasonField")
                        )
                    }
                },
                confirmButton = {
                    Button(
                        enabled = reasonText.isNotBlank(),
                        onClick = {
                            viewModel.submitAppeal(t.type, t.id, reasonText.trim()) { ok ->
                                if (ok) { target = null; reasonText = "" }
                            }
                        }
                    ) { Text("Submit") }
                },
                dismissButton = {
                    Button(onClick = { target = null; reasonText = "" }) { Text("Cancel") }
                }
            )
        }

        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("Hidden Content & Appeals") },
                    navigationIcon = {
                        IconButton(onClick = { navController.popBackStack() }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                        }
                    }
                )
            }
        ) { padding ->
            LazyColumn(modifier = Modifier.fillMaxSize().padding(padding)) {
                item {
                    SectionHeader("Hidden Content")
                    if (hiddenPosts.isEmpty() && hiddenComments.isEmpty()) {
                        MutedText("None of your content is hidden.")
                    }
                }
                items(hiddenPosts, key = { it.postIdentifier }) { post ->
                    HiddenRow(text = post.caption, reason = post.hiddenReason, hasAppeal = post.hasAppeal) {
                        target = AppealTarget("post", post.postIdentifier, post.caption)
                    }
                    HorizontalDivider()
                }
                items(hiddenComments, key = { it.commentIdentifier }) { comment ->
                    HiddenRow(text = comment.body, reason = comment.hiddenReason, hasAppeal = comment.hasAppeal) {
                        target = AppealTarget("comment", comment.commentIdentifier, comment.body)
                    }
                    HorizontalDivider()
                }
                item {
                    SectionHeader("Your Appeals")
                    if (appeals.isEmpty()) {
                        MutedText("You haven't filed any appeals.")
                    }
                }
                items(appeals, key = { it.appealIdentifier }) { appeal ->
                    AppealRow(appeal)
                    HorizontalDivider()
                }
            }
        }
    }
}

@Composable
private fun SectionHeader(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleMedium,
        modifier = Modifier.padding(16.dp)
    )
}

@Composable
private fun MutedText(text: String) {
    Text(text = text, color = Color.Gray, modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp))
}

@Composable
private fun HiddenRow(text: String, reason: String, hasAppeal: Boolean, onAppeal: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(16.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(text, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text(hiddenReasonLabel(reason), style = MaterialTheme.typography.bodySmall, color = Color.Gray)
        }
        Spacer(Modifier.width(8.dp))
        if (hasAppeal) {
            Text("Appealed", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
        } else {
            Button(onClick = onAppeal, modifier = Modifier.testTag("appealButton")) { Text("Appeal") }
        }
    }
}

@Composable
private fun AppealRow(appeal: MyAppeal) {
    Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
        Text(appeal.contentSnapshot ?: appeal.targetType ?: "Appeal", maxLines = 2, overflow = TextOverflow.Ellipsis)
        Text("Reason: ${appeal.reason}", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
        appeal.resolutionNote?.takeIf { it.isNotBlank() }?.let {
            Text("Note: $it", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
        }
        Text(
            appeal.status.replaceFirstChar { it.uppercase() },
            style = MaterialTheme.typography.labelMedium
        )
    }
}

@Preview(showBackground = true)
@Composable
fun AppealsScreenPreview() {
    AppealsScreen(
        navController = rememberNavController(),
        api = PreviewHelpers.mockApi,
        keychainHelper = PreviewHelpers.mockKeychainHelper
    )
}
