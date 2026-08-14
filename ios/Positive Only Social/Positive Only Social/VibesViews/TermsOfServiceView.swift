//
//  TermsOfServiceView.swift
//  Positive Only Social
//
//  The terms of service (issue #493), shown as a sheet from Settings and from
//  the register screen. The privacy policy fits in an alert; the terms run to
//  ten sections, so they get a scrollable screen instead. Same text as
//  https://smiling.social/terms-of-service.
//

import SwiftUI

struct TermsOfServiceView: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Text("Last updated \(GVOAppConstants.termsOfServiceLastUpdated)")
                        .font(.footnote)
                        .foregroundColor(.secondary)

                    ForEach(GVOAppConstants.termsOfServiceSections) { section in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(section.heading)
                                .font(.headline)
                            Text(section.body)
                                .font(.body)
                                .foregroundColor(.secondary)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding()
            }
            .navigationTitle("Terms of Service")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                        .accessibilityIdentifier("TermsOfServiceDoneButton")
                }
            }
        }
        .accessibilityIdentifier("TermsOfServiceView")
    }
}

#Preview {
    TermsOfServiceView()
}
