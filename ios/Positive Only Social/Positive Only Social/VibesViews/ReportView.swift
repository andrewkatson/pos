

import SwiftUI


struct ReportView: View {
    @Environment(\.dismiss) var dismiss
    @State private var reason: String = ""
    
    let onSubmit: (String) -> Void
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Provide a Reason")) {
                    TextField("Reason for reporting...", text: $reason)
                        .accessibilityIdentifier("ProvideAReasonTextField")
                }

                Button("Submit Report") {
                    if !reason.isEmpty {
                        onSubmit(reason)
                        dismiss()
                    }
                }
                .tint(.red)
                .accessibilityIdentifier("SubmitReportButton")
            }
            .navigationTitle("Report Item")
            .scrollDismissesKeyboard(.immediately)
            .navigationBarItems(leading: Button("Cancel") {
                dismiss()
            })
        }
    }
}
#Preview {
    ReportView(onSubmit: { _ in })
}
