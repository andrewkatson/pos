//
//  KeyboardDismiss.swift
//  Positive Only Social
//
//  Shared helper for dismissing the software keyboard so the user can reach
//  the buttons (Login, Register, Share Post, …) that the keyboard would
//  otherwise cover. See issue #205.
//
//  Dismissal must go through SwiftUI's focus system: resigning the first
//  responder behind SwiftUI's back doesn't stick — its focus system
//  immediately re-presents the keyboard (observed on iOS 26). So screens
//  clear an `@FocusState` binding instead. Pressing return/Done on a
//  single-line field already ends editing through that same system, so no
//  extra handling is needed for the return key; scrollable screens
//  additionally use `.scrollDismissesKeyboard` for drag-to-dismiss.
//

import SwiftUI

extension View {
    /// Adds a tap gesture across the receiver's bounds that lets the user tap
    /// outside a text field to put the keyboard away. The caller's action must
    /// clear the screen's `@FocusState` (e.g. `{ focusedField = nil }`) — the
    /// SwiftUI-sanctioned dismissal; see the note at the top of this file.
    ///
    /// The gesture lives on the container, so it never interferes with focusing
    /// a text field or tapping a button — interactive controls consume their
    /// own taps and this only fires for taps that reach the container. A tap
    /// landing on a decorative, hit-testable child (e.g. a `Text` title) is
    /// consumed by that child and won't reach here; mark such children
    /// `.allowsHitTesting(false)` so their taps fall through and still dismiss.
    ///
    /// Best suited to fixed layouts (e.g. a `VStack`); scrollable containers
    /// should use `.scrollDismissesKeyboard` instead.
    func dismissKeyboardOnTap(perform dismiss: @escaping () -> Void) -> some View {
        contentShape(Rectangle())
            .onTapGesture(perform: dismiss)
    }
}
