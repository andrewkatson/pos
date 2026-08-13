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
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.positiveonlysocial.data.constants.Constants

/**
 * The terms of service (issue #493), opened from Settings and from the register
 * screen.
 *
 * The privacy policy is one paragraph and fits an ordinary alert; the terms run
 * to ten sections, so they scroll inside the dialog rather than pushing the Ok
 * button off the screen. Mirrors the iOS TermsOfServiceView and the website's
 * /terms-of-service page.
 */
@Composable
fun TermsOfServiceDialog(onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Terms of Service") },
        text = {
            Column(
                modifier = Modifier
                    .heightIn(max = 400.dp)
                    .verticalScroll(rememberScrollState())
            ) {
                Text(
                    text = "Last updated ${Constants.TERMS_OF_SERVICE_LAST_UPDATED}",
                    style = MaterialTheme.typography.bodySmall
                )
                Constants.TERMS_OF_SERVICE_SECTIONS.forEach { section ->
                    Spacer(modifier = Modifier.height(12.dp))
                    Text(
                        text = section.heading,
                        style = MaterialTheme.typography.titleSmall
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = section.body,
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }
        },
        confirmButton = {
            Button(onClick = onDismiss) {
                Text("Ok")
            }
        }
    )
}
