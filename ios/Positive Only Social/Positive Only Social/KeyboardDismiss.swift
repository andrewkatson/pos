//
//  KeyboardDismiss.swift
//  Positive Only Social
//
//  Shared helpers for dismissing the software keyboard so the user can reach
//  the buttons (Login, Register, Share Post, …) that the keyboard would
//  otherwise cover. See issue #205.
//

import SwiftUI

#if canImport(UIKit)
import UIKit

extension View {
    /// Dismisses the software keyboard by resigning the first responder.
    ///
    /// Use this only where SwiftUI is already ending editing anyway (e.g. an
    /// `.onSubmit` handler, where the return key is closing the keyboard).
    /// Do NOT use it to force-dismiss while a field is still focused: SwiftUI's
    /// focus system doesn't know about the resignation and immediately
    /// re-presents the keyboard (observed on iOS 26). To force-dismiss, clear
    /// the screen's `@FocusState` instead — see `dismissKeyboardOnTap(perform:)`.
    func hideKeyboard() {
        UIApplication.shared.sendAction(
            #selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
    }

    /// Adds a tap gesture across the receiver's bounds that lets the user tap
    /// outside a text field to put the keyboard away. The caller's action must
    /// clear the screen's `@FocusState` (e.g. `{ focusedField = nil }`) — that
    /// is the SwiftUI-sanctioned dismissal; resigning the first responder
    /// behind SwiftUI's back gets undone by its focus system re-presenting the
    /// keyboard (observed on iOS 26).
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
#endif
