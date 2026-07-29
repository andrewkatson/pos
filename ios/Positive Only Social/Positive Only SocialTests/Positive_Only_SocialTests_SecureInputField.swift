//
//  Positive_Only_SocialTests_SecureInputField.swift
//  Positive Only Social
//
//  Regression coverage for issue #301: a plain SecureField wipes its contents
//  on the first edit after it regains focus. SecureInputField prevents that by
//  applying every edit itself and returning `false` from the delegate, so UIKit
//  never performs the mutation that triggers its secure clear-on-reedit. These
//  tests exercise that exact mechanism deterministically (no UI, no timing), so
//  a future refactor that reintroduces the clearing behavior fails here.
//

import Testing
import SwiftUI
import UIKit
@testable import Positive_Only_Social

@MainActor
struct Positive_Only_SocialTests_SecureInputField {

    /// Wires a Coordinator to a mutable string the way SecureInputField wires it
    /// to its `@Binding`, and returns a reader for the current bound value.
    private func makeCoordinator(
        initial: String
    ) -> (SecureInputField.Coordinator, UITextField, () -> String) {
        var value = initial
        let binding = Binding<String>(get: { value }, set: { value = $0 })
        let coordinator = SecureInputField.Coordinator(text: binding, onSubmit: nil)
        let field = UITextField()
        field.isSecureTextEntry = true
        field.text = initial
        return (coordinator, field, { value })
    }

    @Test("Typing after refocus preserves the existing secure text (issue #301)")
    func appendPreservesExistingText() {
        let (coordinator, field, current) = makeCoordinator(initial: "Passw0rd!")

        // The first keystroke after refocus: UIKit asks the delegate whether to
        // change characters. The Coordinator applies the edit itself and returns
        // false, so UIKit's clear-the-secure-field-on-reedit path never runs.
        let end = NSRange(location: ("Passw0rd!" as NSString).length, length: 0)
        let shouldChange = coordinator.textField(
            field, shouldChangeCharactersIn: end, replacementString: "X"
        )

        #expect(shouldChange == false)
        #expect(field.text == "Passw0rd!X")
        #expect(current() == "Passw0rd!X")
    }

    @Test("Inserting in the middle preserves the surrounding text")
    func midInsertPreservesText() {
        let (coordinator, field, current) = makeCoordinator(initial: "abcdef")
        let mid = NSRange(location: 3, length: 0)
        _ = coordinator.textField(field, shouldChangeCharactersIn: mid, replacementString: "-")
        #expect(field.text == "abc-def")
        #expect(current() == "abc-def")
    }

    @Test("Deleting a character removes only that character")
    func deletePreservesRest() {
        let (coordinator, field, current) = makeCoordinator(initial: "abcdef")
        let last = NSRange(location: 5, length: 1) // backspace over 'f'
        _ = coordinator.textField(field, shouldChangeCharactersIn: last, replacementString: "")
        #expect(field.text == "abcde")
        #expect(current() == "abcde")
    }

    @Test("Replacing a selection swaps just the selected range")
    func replaceSelection() {
        let (coordinator, field, current) = makeCoordinator(initial: "abcdef")
        let selection = NSRange(location: 2, length: 2) // replace "cd"
        _ = coordinator.textField(field, shouldChangeCharactersIn: selection, replacementString: "XY")
        #expect(field.text == "abXYef")
        #expect(current() == "abXYef")
    }
}
