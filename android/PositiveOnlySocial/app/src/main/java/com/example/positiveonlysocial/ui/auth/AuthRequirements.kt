package com.example.positiveonlysocial.ui.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

/**
 * Client-side mirrors of the backend validation patterns in
 * backend/user_system/constants.py. Keeping these in one place lets the live
 * requirement hints and the form-validity checks share a single source of
 * truth so they can never drift apart.
 *
 *   password     = ^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[@#$%^&+=_])(?=\S+$).{8,}$
 *   alphanumeric = ^\w{10,500}$   (used for usernames)
 */
data class Requirement(val label: String, val met: Boolean)

object AuthRequirements {
    private const val SPECIAL_CHARS = "@#\$%^&+=_"

    fun password(password: String): List<Requirement> = listOf(
        Requirement("At least 8 characters", password.length >= 8),
        Requirement("At least one number", password.any { it.isDigit() }),
        Requirement("At least one lowercase letter", password.any { it.isLowerCase() }),
        Requirement("At least one uppercase letter", password.any { it.isUpperCase() }),
        Requirement("At least one special character ($SPECIAL_CHARS)", password.any { it in SPECIAL_CHARS }),
        Requirement("No spaces", password.isNotEmpty() && password.none { it.isWhitespace() }),
    )

    fun username(username: String): List<Requirement> = listOf(
        Requirement("Between 10 and 500 characters", username.length in 10..500),
        Requirement(
            "Letters, numbers, and underscores only",
            username.isNotEmpty() && username.all { it.isLetterOrDigit() || it == '_' },
        ),
    )

    fun allMet(requirements: List<Requirement>): Boolean = requirements.all { it.met }
}

/**
 * Renders a checklist of validation requirements. The met/unmet state is shown
 * with color + a ✓/✗ glyph, and conveyed to assistive tech via a per-row
 * content description.
 */
@Composable
fun RequirementHints(requirements: List<Requirement>) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        requirements.forEach { requirement ->
            Text(
                text = "${if (requirement.met) "✓" else "✗"} ${requirement.label}",
                color = if (requirement.met) Color(0xFF4CAF50)
                        else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f),
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.semantics {
                    contentDescription =
                        "${requirement.label}: ${if (requirement.met) "met" else "not met"}"
                },
            )
        }
    }
}
