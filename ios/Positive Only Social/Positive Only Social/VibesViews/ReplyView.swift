
import SwiftUI

/// A view presented as a sheet for replying to a comment thread.
struct ReplyView: View {
      @Environment(\.dismiss) var dismiss
      
      /// The thread being replied to (passed in).
      let thread: CommentThreadViewData
      
      /// The action to perform when "Send" is tapped.
      let onSubmit: (String) -> Void
      
      /// Local state to hold the text being typed.
      @State private var replyText: String = ""
      
      var body: some View {
          NavigationView {
              Form {
                  Section(header: Text("Replying to \(thread.comments.first?.authorUsername ?? "Comment")")) {
                      TextEditor(text: $replyText)
                          .frame(minHeight: 150)
                      CharacterCounter(text: replyText, max: GVOAppConstants.maxCommentLength)
                  }
              }
              .navigationTitle("Post Reply")
              .navigationBarTitleDisplayMode(.inline)
              .scrollDismissesKeyboard(.immediately)
              .toolbar {
                  ToolbarItem(placement: .cancellationAction) {
                      Button("Cancel") {
                          dismiss()
                      }
                  }
                  ToolbarItem(placement: .confirmationAction) {
                      Button("Send") {
                          onSubmit(replyText)
                          dismiss()
                      }
                      .disabled(replyText.isEmpty || !isWithinLength(replyText, max: GVOAppConstants.maxCommentLength))
                  }
              }
          }
      }
  }

