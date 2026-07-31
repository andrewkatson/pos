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

    private func commitFreeform() {
        let terms = parsedInput
        if !terms.isEmpty { onAddFreeform(terms) }
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
                        .disabled(isBusy || parsedInput.isEmpty)
                }

                Text("Separate multiple with commas. Each is checked to keep things positive.")
                    .font(.caption)
                    .foregroundColor(.secondary)

                if input.count > 0 {
                    CharacterCounter(text: input, max: GVOAppConstants.maxFreeformInterestLength)
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
