package com.example.positiveonlysocial.ui

import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalFocusManager

/**
 * Clears focus — and so hides the software keyboard — when the user taps
 * anywhere on this composable that isn't an interactive child such as a text
 * field or button. This lets the user tap outside a field to put the keyboard
 * away so the buttons it was covering (Login, Register, Share Post, …) become
 * reachable again. See issue #205.
 *
 * Interactive children receive their own taps first, so tapping a button or
 * focusing another field keeps working as before — only taps on otherwise-empty
 * space dismiss the keyboard. `detectTapGestures` only reacts to taps, so this
 * does not interfere with scrolling when applied to a scrollable container.
 */
@Composable
fun Modifier.dismissKeyboardOnTap(): Modifier {
    val focusManager = LocalFocusManager.current
    return this.pointerInput(Unit) {
        detectTapGestures(onTap = { focusManager.clearFocus() })
    }
}
