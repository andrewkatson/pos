//
//  AppealsView.swift
//  Positive Only Social
//
//  Lists the signed-in user's own hidden posts and comments (each appealable
//  once) and the status of appeals they have filed. Reached from Settings.
//

import SwiftUI

struct AppealsView: View {
    @StateObject private var viewModel: AppealsViewModel
    @State private var appealTarget: AppealTarget?
    @State private var reasonText = ""

    init(api: Networking, keychainHelper: KeychainHelperProtocol) {
        _viewModel = StateObject(wrappedValue: AppealsViewModel(api: api, keychainHelper: keychainHelper))
    }

    /// The hidden item currently being appealed (drives the reason sheet).
    struct AppealTarget: Identifiable {
        let id = UUID()
        let type: String   // "post" or "comment"
        let targetId: String
        let preview: String
    }

    var body: some View {
        List {
            Section("Hidden Content") {
                if viewModel.hiddenPosts.isEmpty && viewModel.hiddenComments.isEmpty {
                    Text("None of your content is hidden.").foregroundColor(.gray)
                }
                ForEach(viewModel.hiddenPosts) { post in
                    hiddenRow(text: post.caption, reason: post.hiddenReason, hasAppeal: post.hasAppeal) {
                        appealTarget = AppealTarget(type: "post", targetId: post.postIdentifier, preview: post.caption)
                    }
                }
                ForEach(viewModel.hiddenComments) { comment in
                    hiddenRow(text: comment.body, reason: comment.hiddenReason, hasAppeal: comment.hasAppeal) {
                        appealTarget = AppealTarget(type: "comment", targetId: comment.commentIdentifier, preview: comment.body)
                    }
                }
            }

            Section("Your Appeals") {
                if viewModel.appeals.isEmpty {
                    Text("You haven't filed any appeals.").foregroundColor(.gray)
                }
                ForEach(viewModel.appeals) { appeal in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(appeal.contentSnapshot ?? appeal.targetType ?? "Appeal")
                        Text("Reason: \(appeal.reason)").font(.caption).foregroundColor(.gray)
                        if let note = appeal.resolutionNote, !note.isEmpty {
                            Text("Note: \(note)").font(.caption).foregroundColor(.gray)
                        }
                        Text(appeal.status.capitalized).font(.caption).bold()
                    }
                }
            }
        }
        .navigationTitle("Hidden Content & Appeals")
        .navigationBarTitleDisplayMode(.inline)
        .task { await viewModel.load() }
        .refreshable { await viewModel.load() }
        .sheet(item: $appealTarget) { target in appealSheet(target) }
        .alert("Error", isPresented: Binding(
            get: { viewModel.errorMessage != nil },
            set: { if !$0 { viewModel.errorMessage = nil } }
        )) {
            Button("OK", role: .cancel) { viewModel.errorMessage = nil }
        } message: {
            Text(viewModel.errorMessage ?? "")
        }
    }

    private func reasonLabel(_ reason: String) -> String {
        switch reason {
        case "classifier": return "Flagged by automated review"
        case "reports": return "Hidden after user reports"
        default: return "Hidden"
        }
    }

    @ViewBuilder
    private func hiddenRow(text: String, reason: String, hasAppeal: Bool, onAppeal: @escaping () -> Void) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(text).lineLimit(2)
                Text(reasonLabel(reason)).font(.caption).foregroundColor(.gray)
            }
            Spacer()
            if hasAppeal {
                Text("Appealed").font(.caption).foregroundColor(.gray)
            } else {
                Button("Appeal") { onAppeal() }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                    .accessibilityIdentifier("AppealButton")
            }
        }
    }

    @ViewBuilder
    private func appealSheet(_ target: AppealTarget) -> some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                Text(target.preview).font(.subheadline).foregroundColor(.gray)
                TextField("Why should this be restored?", text: $reasonText, axis: .vertical)
                    .lineLimit(3...6)
                    .textFieldStyle(.roundedBorder)
                    .accessibilityIdentifier("AppealReasonField")
                Spacer()
            }
            .padding()
            .navigationTitle("Appeal this \(target.type)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismissSheet() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Submit") {
                        Task {
                            let ok = await viewModel.submitAppeal(
                                targetType: target.type, targetIdentifier: target.targetId, reason: reasonText)
                            if ok { dismissSheet() }
                        }
                    }
                    .disabled(reasonText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    .accessibilityIdentifier("SubmitAppealButton")
                }
            }
        }
        .presentationDetents([.medium])
    }

    private func dismissSheet() {
        appealTarget = nil
        reasonText = ""
    }
}

#Preview {
    NavigationStack {
        AppealsView(api: PreviewHelpers.api, keychainHelper: PreviewHelpers.keychainHelper)
    }
}
