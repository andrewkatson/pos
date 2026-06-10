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

/// Resigns the current first responder, putting the software keyboard away.
/// Single source of truth for the dismissal so the tap and submit paths can't
/// diverge.
private func resignFirstResponder() {
    UIApplication.shared.sendAction(
        #selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
}

extension View {
    /// Dismisses the software keyboard.
    ///
    /// Handy from an `.onSubmit { hideKeyboard() }` handler so that pressing the
    /// keyboard's return/Done key finishes editing.
    func hideKeyboard() {
        resignFirstResponder()
    }

    /// Dismisses the keyboard when the user taps anywhere outside a text field,
    /// so the buttons it was covering become reachable again.
    ///
    /// A plain SwiftUI `.onTapGesture` on the container only fires for taps that
    /// land on empty space — a tap that lands directly on a hit-testable child
    /// such as a `Text` label or `Image` is consumed by that child and never
    /// reaches the container's gesture, so the keyboard would stay up. To make
    /// "tap anywhere outside a field" actually mean *anywhere*, this drops down
    /// to a UIKit tap recognizer installed on the host window that:
    ///   - ignores taps on text-input views, so tapping a field still focuses it;
    ///   - leaves every other touch untouched (`cancelsTouchesInView = false`),
    ///     so buttons and other controls keep working.
    /// Best suited to fixed layouts (e.g. a `VStack`); scrollable containers
    /// should pair `.onSubmit { hideKeyboard() }` with `.scrollDismissesKeyboard`.
    func dismissKeyboardOnTap() -> some View {
        background(KeyboardDismissTapInstaller())
    }
}

/// Installs a non-consuming tap recognizer on the host window. See
/// `dismissKeyboardOnTap()` for why a UIKit recognizer is used instead of a
/// SwiftUI `.onTapGesture`.
private struct KeyboardDismissTapInstaller: UIViewRepresentable {
    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> UIView {
        // A zero-cost, non-interactive probe whose only job is to give us a
        // handle on the window once the view is in the hierarchy.
        let probe = UIView()
        probe.isUserInteractionEnabled = false
        probe.backgroundColor = .clear
        // The view has no window yet at make time; attach on the next runloop.
        DispatchQueue.main.async { [weak probe] in
            context.coordinator.attach(to: probe?.window)
        }
        return probe
    }

    func updateUIView(_ uiView: UIView, context: Context) {
        // Re-attach if the window changed (e.g. after navigation).
        DispatchQueue.main.async { [weak uiView] in
            context.coordinator.attach(to: uiView?.window)
        }
    }

    static func dismantleUIView(_ uiView: UIView, coordinator: Coordinator) {
        coordinator.detach()
    }

    final class Coordinator: NSObject, UIGestureRecognizerDelegate {
        private weak var window: UIWindow?
        private var recognizer: UITapGestureRecognizer?

        func attach(to window: UIWindow?) {
            guard let window, window !== self.window else { return }
            detach()
            let tap = UITapGestureRecognizer(target: self, action: #selector(handleTap))
            tap.cancelsTouchesInView = false
            tap.delegate = self
            window.addGestureRecognizer(tap)
            self.window = window
            self.recognizer = tap
        }

        func detach() {
            if let recognizer { window?.removeGestureRecognizer(recognizer) }
            recognizer = nil
            window = nil
        }

        @objc private func handleTap() {
            resignFirstResponder()
        }

        // Ignore taps that land on a text-input view so that tapping a field
        // focuses it rather than immediately dismissing the keyboard.
        func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer,
                               shouldReceive touch: UITouch) -> Bool {
            var view = touch.view
            while let candidate = view {
                if candidate is UITextField || candidate is UITextView {
                    return false
                }
                view = candidate.superview
            }
            return true
        }

        // Observe taps without disrupting any other recognizer (buttons,
        // scroll views, the text fields' own taps).
        func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer,
                               shouldRecognizeSimultaneouslyWith other: UIGestureRecognizer) -> Bool {
            true
        }
    }
}
#endif
