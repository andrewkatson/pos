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
 *   password     = ^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=\S+$).{8,}$
 *   alphanumeric = ^\w{10,500}$   (used for usernames)
 */
/**
 * A single labelled validation rule. [optional] suggestions don't gate form
 * validity (see [AuthRequirements.allMet]) and render in a neutral state rather
 * than as a pass/fail requirement.
 */
data class Requirement(
    val label: String,
    val didMeetRequirement: Boolean,
    val optional: Boolean = false,
)

object AuthRequirements {


    fun password(password: String): List<Requirement> = listOf(
        Requirement("At least 8 characters", password.length >= 8),
        Requirement("At least one number", password.any { it.isDigit() }),
        Requirement("At least one lowercase letter", password.any { it.isLowerCase() }),
        Requirement("At least one uppercase letter", password.any { it.isUpperCase() }),
        // Any non-alphanumeric character counts (the backend accepts them all).
        // isLetterOrDigit is Unicode-aware so accented letters aren't flagged.
        Requirement(
            "Adding special characters (like ! @ # \$ % ^ & * - _) is suggested",
            password.any { !it.isLetterOrDigit() && !it.isWhitespace() },
            optional = true,
        ),
        Requirement("No spaces", password.isNotEmpty() && password.none { it.isWhitespace() }),
    )

    fun username(username: String): List<Requirement> = listOf(
        Requirement("Between 10 and 500 characters", username.length in 10..500),
        Requirement(
            "Letters, numbers, and underscores only",
            username.isNotEmpty() && username.all { it.isLetterOrDigit() || it == '_' },
        ),
    )

    // Optional suggestions are advisory only and never block submission.
    fun allMet(requirements: List<Requirement>): Boolean =
        requirements.filterNot { it.optional }.all { it.didMeetRequirement }
}

/**
 * Renders a checklist of validation requirements. Required rows show a met/unmet
 * state with color + a ✓/✗ glyph and a per-row content description. Optional
 * suggestions never render as "failed": until satisfied they sit in a neutral
 * state (• / "optional"), switching to met once present.
 */
@Composable
fun RequirementHints(requirements: List<Requirement>) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        requirements.forEach { requirement ->
            val glyph = when {
                requirement.didMeetRequirement -> "✓"
                requirement.optional -> "•"
                else -> "✗"
            }
            val status = when {
                requirement.didMeetRequirement -> "met"
                requirement.optional -> "optional"
                else -> "not met"
            }
            Text(
                text = "$glyph ${requirement.label}",
                color = if (requirement.didMeetRequirement) Color(0xFF4CAF50)
                        else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f),
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.semantics {
                    contentDescription = "${requirement.label}: $status"
                },
            )
        }
    }
}
