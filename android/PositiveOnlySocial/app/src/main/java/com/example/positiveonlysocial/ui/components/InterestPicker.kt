package com.example.positiveonlysocial.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.InputChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import com.example.positiveonlysocial.data.model.InterestOption
import com.example.positiveonlysocial.data.model.InterestVocabulary
import com.example.positiveonlysocial.data.model.RejectedInterest

/**
 * The positive-interest picker (issues #446/#35): preset buckets as toggleable
 * chips plus a freeform entry that accepts a single term or a comma-separated
 * list. Reused by the Settings dialog (prefilled, removable) and the
 * registration screen (empty, add-only). Value-in + callbacks-out.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun InterestPicker(
    options: List<InterestOption>,
    selectedSlugs: List<String>,
    freeformTerms: List<String>,
    rejected: List<RejectedInterest>,
    isBusy: Boolean,
    onToggle: (String) -> Unit,
    onAddFreeform: (List<String>) -> Unit,
    onRemoveFreeform: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var input by remember { mutableStateOf("") }
    val parsed = InterestVocabulary.parseFreeform(input)
    // Gate on the backend's per-term limit like the other length-limited inputs
    // (ProfileScreen's bio editor uses isWithinLength the same way). Without it
    // a too-long term is accepted into the list only to be dropped server-side —
    // and at registration the rejection isn't surfaced at all, so it would
    // vanish silently.
    // Also gate on the count cap: the parent silently drops anything past it
    // while commit() clears the input regardless, so without this the user's
    // text just disappears. Counts only terms not already listed, matching the
    // parent's case-insensitive dedupe — re-typing an existing term shouldn't
    // consume room.
    val alreadyListed = freeformTerms.map { it.lowercase() }.toSet()
    val newTermCount = parsed.count { !alreadyListed.contains(it.lowercase()) }
    val hasRoom = freeformTerms.size + newTermCount <= InterestVocabulary.MAX_FREEFORM_INTERESTS
    val canAdd = parsed.isNotEmpty() && hasRoom &&
        parsed.all { isWithinLength(it, InterestVocabulary.MAX_FREEFORM_INTEREST_LENGTH) }
    // The limit is per term, not per entry, so the counter tracks the longest
    // parsed term — otherwise a comma-separated list of short terms would read
    // as over the limit while Add (correctly) stayed enabled.
    val longestTerm = parsed.maxByOrNull { it.length } ?: input

    fun commit() {
        // Guarded here too, not just on the button: the Done key reaches this
        // directly. A blocked commit keeps the input so the user can shorten it.
        if (!canAdd) return
        onAddFreeform(parsed)
        input = ""
    }

    Column(modifier = modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Pick what you find positive", style = MaterialTheme.typography.titleSmall)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            options.forEach { option ->
                FilterChip(
                    selected = selectedSlugs.contains(option.slug),
                    onClick = { onToggle(option.slug) },
                    label = { Text(option.name) },
                    enabled = !isBusy
                )
            }
        }

        Text("Add your own", style = MaterialTheme.typography.titleSmall)
        if (freeformTerms.isNotEmpty()) {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                freeformTerms.forEach { term ->
                    InputChip(
                        selected = true,
                        onClick = { if (!isBusy) onRemoveFreeform(term) },
                        label = { Text(term) },
                        enabled = !isBusy,
                        trailingIcon = {
                            Icon(Icons.Default.Close, contentDescription = "Remove $term")
                        }
                    )
                }
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                singleLine = true,
                enabled = !isBusy,
                placeholder = { Text("e.g. hiking, jazz, baking") },
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { commit() }),
                modifier = Modifier.weight(1f)
            )
            Button(onClick = { commit() }, enabled = !isBusy && canAdd) {
                Text("Add")
            }
        }

        Text(
            "Separate multiple with commas. Each is checked to keep things positive.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        // Inline guidance so the disabled Add button isn't a dead end (the
        // counter plays that role for the length limit).
        if (!hasRoom) {
            Text(
                if (freeformTerms.size >= InterestVocabulary.MAX_FREEFORM_INTERESTS)
                    "You've added the maximum of ${InterestVocabulary.MAX_FREEFORM_INTERESTS} interests. Remove one to add another."
                else
                    "That's more than the ${InterestVocabulary.MAX_FREEFORM_INTERESTS}-interest maximum. Remove one, or add fewer at once.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        if (input.isNotEmpty()) {
            CharacterCounter(text = longestTerm, max = InterestVocabulary.MAX_FREEFORM_INTEREST_LENGTH)
        }

        if (rejected.isNotEmpty()) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                rejected.forEach { item ->
                    Text(
                        "“${item.text}” ${item.reason ?: "was not added"}.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(top = 2.dp)
                    )
                }
            }
        }
    }
}
