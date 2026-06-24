//
//  CharacterCounter.swift
//  Positive Only Social
//

import SwiftUI

/// Fraction of a length limit at which the counter starts warning the user that
/// they are getting close (mirrored across web and Android).
private let nearLimitFraction: Double = 0.9

/// Counts unicode scalars (code points) rather than grapheme clusters, so the
/// count matches Python's `len()` on the backend (which is what the server
/// enforces). e.g. "💚" is one code point here, like it is one character
/// server-side.
func characterCount(_ text: String) -> Int {
    text.unicodeScalars.count
}

/// Whether `text` is within `max` code points — used to gate submit buttons so
/// the client never sends content the backend would reject for length.
func isWithinLength(_ text: String, max: Int) -> Bool {
    characterCount(text) <= max
}

/// A live "count / max" indicator mirroring the backend length limits
/// (backend/user_system/constants.py). Turns amber as the user nears the limit
/// and red once over it.
struct CharacterCounter: View {
    let text: String
    let max: Int

    private var count: Int { characterCount(text) }
    private var isOver: Bool { count > max }
    private var isNear: Bool { !isOver && Double(count) >= Double(max) * nearLimitFraction }

    private var color: Color {
        if isOver { return .red }
        if isNear { return .orange }
        return .secondary
    }

    var body: some View {
        Text(isOver ? "\(count - max) over the \(max) character limit" : "\(count) / \(max)")
            .font(.caption)
            .foregroundColor(color)
            .frame(maxWidth: .infinity, alignment: .trailing)
    }
}
