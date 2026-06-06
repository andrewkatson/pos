//
//  AuthRequirements.swift
//  Positive Only Social
//
//  Client-side mirrors of the backend validation patterns in
//  backend/user_system/constants.py. Keeping these in one place lets the live
//  requirement hints and the form-validity checks share a single source of
//  truth so they can never drift apart.
//
//    password     = ^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[@#$%^&+=_])(?=\S+$).{8,}$
//    alphanumeric = ^\w{10,500}$   (used for usernames)
//

import Foundation
import SwiftUI

enum AuthRequirements {
    /// A single labelled validation rule and whether the current input satisfies it.
    struct Requirement: Identifiable {
        let label: String
        let met: Bool
        var id: String { label }
    }

    private static func matches(_ value: String, _ pattern: String) -> Bool {
        value.range(of: pattern, options: .regularExpression) != nil
    }

    static func password(_ pwd: String) -> [Requirement] {
        [
            Requirement(label: "At least 8 characters", met: pwd.count >= 8),
            Requirement(label: "At least one number", met: matches(pwd, "[0-9]")),
            Requirement(label: "At least one lowercase letter", met: matches(pwd, "[a-z]")),
            Requirement(label: "At least one uppercase letter", met: matches(pwd, "[A-Z]")),
            Requirement(label: "At least one special character (@#$%^&+=_)", met: matches(pwd, "[@#$%^&+=_]")),
            Requirement(label: "No spaces", met: !pwd.isEmpty && !matches(pwd, "\\s")),
        ]
    }

    static func username(_ name: String) -> [Requirement] {
        [
            Requirement(label: "Between 10 and 500 characters", met: name.count >= 10 && name.count <= 500),
            Requirement(label: "Letters, numbers, and underscores only", met: matches(name, "^\\w+$")),
        ]
    }

    static func allMet(_ requirements: [Requirement]) -> Bool {
        requirements.allSatisfy { $0.met }
    }
}

/// Renders a checklist of validation requirements. The met/unmet state is shown
/// with color + an SF Symbol, and conveyed to assistive tech via a per-row
/// accessibility label. Shared across the auth screens so the labels, colors,
/// and accessibility behavior can't drift.
struct RequirementHints: View {
    let requirements: [AuthRequirements.Requirement]

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            ForEach(requirements) { requirement in
                Label(
                    requirement.label,
                    systemImage: requirement.met ? "checkmark.circle.fill" : "xmark.circle"
                )
                .foregroundColor(requirement.met ? .green : .secondary)
                .font(.caption)
                .accessibilityLabel("\(requirement.label): \(requirement.met ? "met" : "not met")")
            }
        }
    }
}
