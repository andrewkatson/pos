package com.example.positiveonlysocial.ui.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.DialogProperties
import com.example.positiveonlysocial.data.constants.Constants

/**
 * Asks a signed-in user to accept the privacy policy again before using the app
 * (issue #620). Mirrors the iOS "Privacy Policy Updated" alert and the website's
 * PrivacyPolicyReacceptGate.
 *
 * It can't be dismissed by tapping outside or pressing back: the only ways out
 * are accepting it or logging out.
 */
@Composable
fun PrivacyPolicyReacceptDialog(onAccept: () -> Unit, onLogOut: () -> Unit) {
    AlertDialog(
        onDismissRequest = { /* A choice is required. */ },
        properties = DialogProperties(dismissOnBackPress = false, dismissOnClickOutside = false),
        title = { Text("Privacy Policy Updated") },
        text = {
            Column(
                modifier = Modifier
                    .heightIn(max = 400.dp)
                    .verticalScroll(rememberScrollState())
            ) {
                Text(
                    text = Constants.PRIVACY_POLICY_UPDATED_INTRO,
                    style = MaterialTheme.typography.bodyMedium
                )
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    text = Constants.PRIVACY_POLICY_TEXT,
                    style = MaterialTheme.typography.bodyMedium
                )
            }
        },
        confirmButton = {
            Button(onClick = onAccept) {
                Text("Accept")
            }
        },
        dismissButton = {
            TextButton(onClick = onLogOut) {
                Text("Log Out")
            }
        }
    )
}
