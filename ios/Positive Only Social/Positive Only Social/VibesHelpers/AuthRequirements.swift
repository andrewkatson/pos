//
//  AuthRequirements.swift
//  Positive Only Social
//
//  Client-side mirrors of the backend validation patterns in
//  backend/user_system/constants.py. Keeping these in one place lets the live
//  requirement hints and the form-validity checks share a single source of
//  truth so they can never drift apart.
//
//    password     = ^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=\S+$).{8,}$
//    alphanumeric = ^\w{10,500}$   (used for usernames)
//

import Foundation
import SwiftUI

enum AuthRequirements {
    /// A single labelled validation rule and whether the current input satisfies it.
    struct Requirement: Identifiable {
        let label: String
        let didMeetRequirement: Bool
        /// Optional suggestions don't gate form validity (see allMet) and render in a
        /// neutral state rather than as a pass/fail requirement.
        var optional: Bool = false
        var id: String { label }
    }

    private static func matches(_ value: String, _ pattern: String) -> Bool {
        value.range(of: pattern, options: .regularExpression) != nil
    }

    static func password(_ pwd: String) -> [Requirement] {
        [
            Requirement(label: "At least 8 characters", didMeetRequirement: pwd.count >= 8),
            Requirement(label: "At least one number", didMeetRequirement: matches(pwd, "[0-9]")),
            Requirement(label: "At least one lowercase letter", didMeetRequirement: matches(pwd, "[a-z]")),
            Requirement(label: "At least one uppercase letter", didMeetRequirement: matches(pwd, "[A-Z]")),
            // Any non-alphanumeric character counts (the backend accepts them all).
            // Unicode-aware so it doesn't flag accented letters as "special".
            Requirement(label: "Adding special characters (like ! @ # $ % ^ & * - _) is suggested", didMeetRequirement: matches(pwd, "[^\\p{L}\\p{N}\\s]"), optional: true),
            Requirement(label: "No spaces", didMeetRequirement: !pwd.isEmpty && !matches(pwd, "\\s")),
        ]
    }

    static func username(_ name: String) -> [Requirement] {
        [
            Requirement(label: "Between 10 and 500 characters", didMeetRequirement: name.count >= 10 && name.count <= 500),
            Requirement(label: "Letters, numbers, and underscores only", didMeetRequirement: matches(name, "^\\w+$")),
        ]
    }

    static func allMet(_ requirements: [Requirement]) -> Bool {
        // Optional suggestions are advisory only and never block submission.
        requirements.filter { !$0.optional }.allSatisfy { $0.didMeetRequirement }
    }
}

/// Renders a checklist of validation requirements. Required rows show a met/unmet
/// state with color + an SF Symbol and a per-row accessibility label. Optional
/// suggestions never render as "failed": until satisfied they sit in a neutral
/// state announced as "optional", switching to "met" once present. Shared across
/// the auth screens so the labels, colors, and accessibility behavior can't drift.
struct RequirementHints: View {
    let requirements: [AuthRequirements.Requirement]

    private func symbol(for requirement: AuthRequirements.Requirement) -> String {
        if requirement.didMeetRequirement { return "checkmark.circle.fill" }
        return requirement.optional ? "circle" : "xmark.circle"
    }

    private func status(for requirement: AuthRequirements.Requirement) -> String {
        if requirement.didMeetRequirement { return "met" }
        return requirement.optional ? "optional" : "not met"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            ForEach(requirements) { requirement in
                Label(
                    requirement.label,
                    systemImage: symbol(for: requirement)
                )
                .foregroundColor(requirement.didMeetRequirement ? .green : .secondary)
                .font(.caption)
                .accessibilityLabel("\(requirement.label): \(status(for: requirement))")
            }
        }
    }
}
