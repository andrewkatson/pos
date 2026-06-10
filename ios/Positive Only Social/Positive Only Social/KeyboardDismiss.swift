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
    /// Resigns the current first responder, putting the software keyboard away.
    ///
    /// Handy from an `.onSubmit { hideKeyboard() }` handler so that pressing the
    /// keyboard's return/Done key finishes editing.
    func hideKeyboard() {
        UIApplication.shared.sendAction(
            #selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
    }

    /// Adds a tap gesture across the receiver's bounds that dismisses the
    /// keyboard, letting the user tap anywhere outside a field to put it away.
    ///
    /// Child controls (buttons, text fields, toggles) receive their own taps
    /// first, so this only fires for taps on otherwise-empty space — tapping a
    /// button or focusing another field keeps working as before. Best suited to
    /// fixed layouts (e.g. a `VStack`); scrollable containers should pair an
    /// `.onSubmit { hideKeyboard() }` with `.scrollDismissesKeyboard` instead.
    func dismissKeyboardOnTap() -> some View {
        contentShape(Rectangle())
            .onTapGesture {
                UIApplication.shared.sendAction(
                    #selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
            }
    }
}
#endif
