//
//  InterestPickerView.swift
//  Positive Only Social
//
//  The positive-interest picker (issues #446/#35): preset buckets as
//  toggleable chips plus a freeform entry that accepts a single term or a
//  comma-separated list. Reused by the Settings sheet (prefilled, removable)
//  and the registration screen (empty, add-only). Value-in + closures-out so
//  it composes with either a view model or local @State.
//

import SwiftUI

struct InterestPickerView: View {
    let options: [InterestOption]
    let selectedSlugs: [String]
    let freeformTerms: [String]
    let rejected: [RejectedInterest]
    let isBusy: Bool
    let onToggle: (String) -> Void
    let onAddFreeform: ([String]) -> Void
    let onRemoveFreeform: (String) -> Void

    @State private var input: String = ""

    private var selectedSet: Set<String> { Set(selectedSlugs) }

    private var parsedInput: [String] { InterestVocabulary.parseFreeform(input) }

    /// Gate on the backend's per-term limit like the other length-limited
    /// composers here (BioComposerView uses isWithinLength the same way).
    /// Without it a too-long term is accepted into the list only to be dropped
    /// server-side — and at registration the rejection isn't surfaced at all,
    /// so it would vanish silently.
    private var canAdd: Bool {
        let terms = parsedInput
        return !terms.isEmpty && hasRoom && terms.allSatisfy {
            isWithinLength($0, max: GVOAppConstants.maxFreeformInterestLength)
        }
    }

    /// The count cap. The parent silently drops anything past it while
    /// commitFreeform clears the input regardless, so without this the user's
    /// text just disappears. Counts only terms not already listed, matching the
    /// parent's case-insensitive dedupe — re-typing an existing term shouldn't
    /// consume room.
    private var hasRoom: Bool {
        let listed = Set(freeformTerms.map { $0.lowercased() })
        let newCount = parsedInput.filter { !listed.contains($0.lowercased()) }.count
        return freeformTerms.count + newCount <= GVOAppConstants.maxFreeformInterests
    }

    /// The limit is per term, not per entry, so the counter tracks the longest
    /// parsed term — otherwise a comma-separated list of short terms would read
    /// as over the limit while Add (correctly) stayed enabled.
    private var longestTerm: String {
        parsedInput.max(by: { $0.count < $1.count }) ?? input
    }

    private func commitFreeform() {
        // Guarded here too, not just on the button: onSubmit reaches this
        // directly. A blocked commit keeps the input so the user can shorten it.
        guard canAdd else { return }
        onAddFreeform(parsedInput)
        input = ""
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Preset buckets
            VStack(alignment: .leading, spacing: 8) {
                Text("Pick what you find positive")
                    .font(.subheadline).fontWeight(.semibold)
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 96), spacing: 8)], alignment: .leading, spacing: 8) {
                    ForEach(options) { option in
                        let isSelected = selectedSet.contains(option.slug)
                        Button {
                            onToggle(option.slug)
                        } label: {
                            Text(option.name)
                                .font(.subheadline)
                                .padding(.vertical, 6)
                                .padding(.horizontal, 12)
                                .frame(maxWidth: .infinity)
                                .background(
                                    Capsule().fill(isSelected ? Color.accentColor : Color.clear)
                                )
                                .overlay(
                                    Capsule().stroke(isSelected ? Color.accentColor : Color.secondary.opacity(0.4), lineWidth: 1)
                                )
                                .foregroundColor(isSelected ? Color.white : Color.primary)
                        }
                        .buttonStyle(.plain)
                        .disabled(isBusy)
                        .accessibilityAddTraits(isSelected ? .isSelected : [])
                    }
                }
            }

            // Freeform entry
            VStack(alignment: .leading, spacing: 8) {
                Text("Add your own")
                    .font(.subheadline).fontWeight(.semibold)

                if !freeformTerms.isEmpty {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 96), spacing: 8)], alignment: .leading, spacing: 8) {
                        ForEach(freeformTerms, id: \.self) { term in
                            HStack(spacing: 6) {
                                Text(term).font(.subheadline).lineLimit(1)
                                Button {
                                    onRemoveFreeform(term)
                                } label: {
                                    Image(systemName: "xmark.circle.fill")
                                        .foregroundColor(.secondary)
                                }
                                .buttonStyle(.plain)
                                .disabled(isBusy)
                                .accessibilityLabel("Remove \(term)")
                            }
                            .padding(.vertical, 4)
                            .padding(.horizontal, 10)
                            .background(Capsule().fill(Color.secondary.opacity(0.15)))
                        }
                    }
                }

                HStack {
                    TextField("e.g. hiking, jazz, baking", text: $input)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .textFieldStyle(.roundedBorder)
                        .disabled(isBusy)
                        .onSubmit(commitFreeform)
                    Button("Add", action: commitFreeform)
                        .disabled(isBusy || !canAdd)
                }

                Text("Separate multiple with commas. Each is checked to keep things positive.")
                    .font(.caption)
                    .foregroundColor(.secondary)

                // Inline guidance so the disabled Add button isn't a dead end
                // (the counter plays that role for the length limit).
                if !hasRoom {
                    Text(freeformTerms.count >= GVOAppConstants.maxFreeformInterests
                         ? "You've added the maximum of \(GVOAppConstants.maxFreeformInterests) interests. Remove one to add another."
                         : "That's more than the \(GVOAppConstants.maxFreeformInterests)-interest maximum. Remove one, or add fewer at once.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                if input.count > 0 {
                    CharacterCounter(text: longestTerm, max: GVOAppConstants.maxFreeformInterestLength)
                }

                if !rejected.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(rejected) { item in
                            Text("“\(item.text)” \(item.reason ?? "was not added").")
                                .font(.caption)
                                .foregroundColor(.red)
                        }
                    }
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }
}
