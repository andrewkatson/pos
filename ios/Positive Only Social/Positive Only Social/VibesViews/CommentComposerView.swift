
import SwiftUI

/// The shared composer sheet for writing a comment — used both for a brand new
/// comment on the post and for replying to a thread (issues #266, #289, #290).
/// It always shows the character counter, and submitting dismisses the sheet
/// (and thus the keyboard) immediately, so tapping the confirm button repeatedly
/// can't post the same comment twice (issue #291).
struct CommentComposerView: View {
      @Environment(\.dismiss) var dismiss

      /// The sheet's title — e.g. "Add Comment" or "Post Reply".
      let title: String

      /// The action to perform when the confirm button is tapped.
      let onSubmit: (String) -> Void

      /// Local state to hold the text being typed.
      @State private var text: String = ""

      var body: some View {
          NavigationView {
              Form {
                  Section {
                      TextEditor(text: $text)
                          .frame(minHeight: 150)
                          .accessibilityIdentifier("CommentComposerTextEditor")
                      CharacterCounter(text: text, max: GVOAppConstants.maxCommentLength)
                  }
              }
              .navigationTitle(title)
              .navigationBarTitleDisplayMode(.inline)
              .scrollDismissesKeyboard(.immediately)
              .toolbar {
                  ToolbarItem(placement: .cancellationAction) {
                      Button("Cancel") {
                          dismiss()
                      }
                  }
                  ToolbarItem(placement: .confirmationAction) {
                      Button("Post") {
                          onSubmit(text)
                          dismiss()
                      }
                      .disabled(text.isEmpty || !isWithinLength(text, max: GVOAppConstants.maxCommentLength))
                      .accessibilityIdentifier("PostCommentButton")
                  }
              }
          }
      }
  }
