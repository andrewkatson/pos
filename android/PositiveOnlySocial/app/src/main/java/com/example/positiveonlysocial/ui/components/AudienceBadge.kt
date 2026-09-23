package com.example.positiveonlysocial.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Public
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.testTag
import androidx.compose.ui.unit.dp
import com.example.positiveonlysocial.data.model.PostAudience

/**
 * A small badge telling the signed-in user who can see one of their own posts
 * or comments (issue #518). Callers render it only on the viewer's own content:
 * who an author chose to share with is the author's information, the same way
 * "who liked this" is (#478), so a third party never sees it.
 *
 * Every tier gets a badge, public included — the point is to answer "who can
 * see this?" at a glance, and a post you meant to keep to family but posted
 * publicly is exactly the case a missing badge would hide.
 *
 * @param audience the raw backend value; null (older responses) reads as public.
 * @param compact icon only, for the three-column profile grid; the description
 * still reaches TalkBack.
 */
@Composable
fun AudienceBadge(
    audience: String?,
    modifier: Modifier = Modifier,
    compact: Boolean = false
) {
    val tier = PostAudience.badgeTier(audience)
    val tint = MaterialTheme.colorScheme.onSurfaceVariant
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(3.dp),
        modifier = modifier
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .padding(horizontal = if (compact) 4.dp else 6.dp, vertical = 2.dp)
            // One accessibility node reading "Visible to ...", rather than an
            // icon with no description followed by a bare "Family".
            .clearAndSetSemantics {
                contentDescription = tier.badgeDescription
                testTag = "AudienceBadge"
            }
    ) {
        Icon(
            imageVector = audienceIcon(tier),
            contentDescription = null,
            tint = tint,
            modifier = Modifier.size(12.dp)
        )
        if (!compact) {
            Text(
                text = tier.badgeLabel,
                style = MaterialTheme.typography.labelSmall,
                color = tint
            )
        }
    }
}

/** The badge's icon, widening as the circle does: one globe, then two people,
 * a group, and home. */
private fun audienceIcon(tier: PostAudience): ImageVector = when (tier) {
    PostAudience.PUBLIC -> Icons.Default.Public
    PostAudience.FOLLOWING -> Icons.Default.People
    PostAudience.FRIENDS -> Icons.Default.Groups
    PostAudience.FAMILY -> Icons.Default.Home
}
