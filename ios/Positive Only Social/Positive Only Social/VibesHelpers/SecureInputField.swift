//
//  SecureInputField.swift
//  Positive Only Social
//
//  A secure text field that preserves its contents across focus changes.
//
//  UIKit's `UITextField` with `isSecureTextEntry` clears any existing text the
//  first time the user edits after the field regains focus — a security default
//  that surprised users on the Set New Password screen: tapping away and back,
//  then typing one more character, wiped everything they had entered (issue
//  #301). SwiftUI's `SecureField` inherits that behavior.
//
//  This wrapper applies every edit itself and returns `false` from the delegate,
//  so UIKit never performs the mutation that triggers the auto-clear. Input is
//  still masked, the element still reports as a secure text field to XCUITest,
//  and the accessibility identifier is set directly on the field so existing UI
//  tests keep finding it.
//

import SwiftUI
import UIKit

struct SecureInputField: UIViewRepresentable {
    let placeholder: String
    @Binding var text: String
    var textContentType: UITextContentType?
    var accessibilityIdentifier: String?
    var onSubmit: (() -> Void)?

    init(
        _ placeholder: String,
        text: Binding<String>,
        textContentType: UITextContentType? = nil,
        accessibilityIdentifier: String? = nil,
        onSubmit: (() -> Void)? = nil
    ) {
        self.placeholder = placeholder
        self._text = text
        self.textContentType = textContentType
        self.accessibilityIdentifier = accessibilityIdentifier
        self.onSubmit = onSubmit
    }

    func makeUIView(context: Context) -> UITextField {
        let field = UITextField()
        field.isSecureTextEntry = true
        field.placeholder = placeholder
        field.textContentType = textContentType
        field.accessibilityIdentifier = accessibilityIdentifier
        field.autocapitalizationType = .none
        field.autocorrectionType = .no
        field.spellCheckingType = .no
        field.borderStyle = .none
        field.returnKeyType = .done
        field.delegate = context.coordinator
        // Backstop for changes that bypass the delegate (e.g. AutoFill / paste):
        // keep the binding in sync so validation doesn't go stale.
        field.addTarget(
            context.coordinator,
            action: #selector(Coordinator.editingChanged(_:)),
            for: .editingChanged
        )
        field.font = UIFont.preferredFont(forTextStyle: .body)
        field.adjustsFontForContentSizeCategory = true
        // Fill the row width like a native SecureField rather than hugging its text.
        field.setContentHuggingPriority(.defaultLow, for: .horizontal)
        field.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        return field
    }

    func updateUIView(_ uiView: UITextField, context: Context) {
        // Reflect external state changes (e.g. a programmatic reset) without
        // clobbering what the user is actively typing.
        if uiView.text != text {
            uiView.text = text
        }
        uiView.placeholder = placeholder
        uiView.textContentType = textContentType
        uiView.accessibilityIdentifier = accessibilityIdentifier
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(text: $text, onSubmit: onSubmit)
    }

    final class Coordinator: NSObject, UITextFieldDelegate {
        @Binding var text: String
        let onSubmit: (() -> Void)?

        init(text: Binding<String>, onSubmit: (() -> Void)?) {
            self._text = text
            self.onSubmit = onSubmit
        }

        // Apply the edit ourselves and return false. Because UIKit never gets to
        // mutate the field, its "clear the secure field on the first edit after
        // refocus" path never runs, so earlier input survives (issue #301).
        func textField(
            _ textField: UITextField,
            shouldChangeCharactersIn range: NSRange,
            replacementString string: String
        ) -> Bool {
            // Secure fields don't offer multistage/IME composition, but guard
            // regardless: while there is marked (mid-composition) text, let UIKit
            // manage the edit so composition keyboards keep working.
            if textField.markedTextRange != nil { return true }
            let current = textField.text ?? ""
            guard let stringRange = Range(range, in: current) else { return false }
            let updated = current.replacingCharacters(in: stringRange, with: string)
            textField.text = updated
            text = updated

            // Keep the caret just after the inserted text. Offsets are UTF-16
            // units, matching NSRange.location and UITextPosition.
            if let caret = textField.position(
                from: textField.beginningOfDocument,
                offset: range.location + (string as NSString).length
            ) {
                textField.selectedTextRange = textField.textRange(from: caret, to: caret)
            }
            return false
        }

        @objc func editingChanged(_ textField: UITextField) {
            let value = textField.text ?? ""
            if text != value { text = value }
        }

        func textFieldShouldReturn(_ textField: UITextField) -> Bool {
            textField.resignFirstResponder()
            onSubmit?()
            return false
        }
    }
}
