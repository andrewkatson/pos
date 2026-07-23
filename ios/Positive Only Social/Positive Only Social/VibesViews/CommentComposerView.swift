
import SwiftUI
import UIKit

/// Per-UTF16-unit formatting for the comment composer (issue #318). Mirrors the
/// web char-attribute model: the toolbar sets attributes over the selection,
/// and on submit the array is compressed into sorted, non-overlapping spans.
private struct CharStyle: Equatable {
    var bold = false
    var italic = false
    var size = "normal"
    var isPlain: Bool { !bold && !italic && size == "normal" }
}

/// Drives the `UITextView`-backed editor: owns the plain text and the parallel
/// per-character style array, applies toolbar actions to the current selection,
/// and exposes the compressed formatting spans.
final class CommentFormatController: ObservableObject {
    @Published private(set) var text: String = ""
    /// The base point size for the editor, honoring Dynamic Type.
    let baseSize: CGFloat = UIFont.preferredFont(forTextStyle: .body).pointSize

    fileprivate weak var textView: UITextView?
    private var styles: [CharStyle] = []

    var isSubmittable: Bool {
        !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && isWithinLength(text, max: GVOAppConstants.maxCommentLength)
    }

    /// The inline formatting spans to submit, or nil when the comment is plain.
    var spans: [CommentFormatSpan]? {
        var result: [CommentFormatSpan] = []
        var i = 0
        while i < styles.count {
            let style = styles[i]
            if style.isPlain { i += 1; continue }
            var j = i + 1
            while j < styles.count && styles[j] == style { j += 1 }
            result.append(CommentFormatSpan(start: i, end: j, bold: style.bold, italic: style.italic, size: style.size))
            i = j
        }
        return result.isEmpty ? nil : result
    }

    // MARK: - Editing

    /// Called by the editor when the user changes the text; reconciles the
    /// style array across the edit and re-renders.
    func userChangedText(_ newText: String) {
        reconcile(to: newText)
        text = newText
        render(selection: textView?.selectedRange)
    }

    func toggleBold() { toggleBool(\.bold) }
    func toggleItalic() { toggleBool(\.italic) }

    func setSize(_ size: String) {
        guard let range = textView?.selectedRange, range.length > 0 else { return }
        let lo = range.location, hi = range.location + range.length
        for i in lo..<hi where i < styles.count { styles[i].size = size }
        render(selection: range)
    }

    private func toggleBool(_ keyPath: WritableKeyPath<CharStyle, Bool>) {
        guard let range = textView?.selectedRange, range.length > 0 else { return }
        let lo = range.location, hi = range.location + range.length
        let allOn = (lo..<hi).allSatisfy { $0 < styles.count && styles[$0][keyPath: keyPath] }
        for i in lo..<hi where i < styles.count { styles[i][keyPath: keyPath] = !allOn }
        render(selection: range)
    }

    // MARK: - Reconciliation & rendering

    private func reconcile(to newText: String) {
        let old = text as NSString
        let new = newText as NSString
        if old.isEqual(to: newText) { return }
        // Keep the style array the same length as the old text before diffing.
        if styles.count != old.length {
            styles = Array(repeating: CharStyle(), count: old.length)
        }
        let oldLen = old.length, newLen = new.length
        let minLen = min(oldLen, newLen)
        var prefix = 0
        while prefix < minLen && old.character(at: prefix) == new.character(at: prefix) { prefix += 1 }
        var suffix = 0
        while suffix < (minLen - prefix)
            && old.character(at: oldLen - 1 - suffix) == new.character(at: newLen - 1 - suffix) {
            suffix += 1
        }
        let head = Array(styles.prefix(prefix))
        let tail = Array(styles.suffix(suffix))
        let insertedCount = max(0, newLen - suffix - prefix)
        let inserted = Array(repeating: CharStyle(), count: insertedCount)
        styles = head + inserted + tail
    }

    /// Rebuilds the editor's attributed text from the plain text + styles,
    /// restoring `selection` (or a trailing caret) afterwards.
    fileprivate func render(selection: NSRange?) {
        guard let textView else { return }
        if styles.count != (text as NSString).length {
            styles = Array(repeating: CharStyle(), count: (text as NSString).length)
        }
        textView.attributedText = makeAttributedText()
        let length = (textView.text as NSString).length
        if let selection {
            let location = min(selection.location, length)
            let selLength = min(selection.length, length - location)
            textView.selectedRange = NSRange(location: location, length: selLength)
        } else {
            textView.selectedRange = NSRange(location: length, length: 0)
        }
    }

    fileprivate func attachIfNeeded(_ textView: UITextView) {
        self.textView = textView
        if textView.attributedText.length == 0 && !text.isEmpty {
            render(selection: nil)
        }
    }

    private func makeAttributedText() -> NSAttributedString {
        let ns = text as NSString
        let result = NSMutableAttributedString()
        var i = 0
        while i < ns.length {
            let style = i < styles.count ? styles[i] : CharStyle()
            var j = i + 1
            while j < ns.length && (j < styles.count ? styles[j] : CharStyle()) == style { j += 1 }
            let piece = ns.substring(with: NSRange(location: i, length: j - i))
            result.append(NSAttributedString(string: piece, attributes: attributes(for: style)))
            i = j
        }
        return result
    }

    private func attributes(for style: CharStyle) -> [NSAttributedString.Key: Any] {
        let size = baseSize * TextFormatting.sizeScale(style.size)
        var font = UIFont.systemFont(ofSize: size)
        var traits: UIFontDescriptor.SymbolicTraits = []
        if style.bold { traits.insert(.traitBold) }
        if style.italic { traits.insert(.traitItalic) }
        if !traits.isEmpty, let descriptor = font.fontDescriptor.withSymbolicTraits(traits) {
            font = UIFont(descriptor: descriptor, size: size)
        }
        return [.font: font, .foregroundColor: UIColor.label]
    }
}

/// A `UITextView`-backed editor that keeps the bound controller in sync with
/// the text and selection so the toolbar can style the selection (issue #318).
private struct FormattedTextEditor: UIViewRepresentable {
    @ObservedObject var controller: CommentFormatController

    func makeUIView(context: Context) -> UITextView {
        let textView = UITextView()
        textView.delegate = context.coordinator
        textView.font = UIFont.systemFont(ofSize: controller.baseSize)
        textView.backgroundColor = .clear
        textView.isScrollEnabled = true
        textView.accessibilityIdentifier = "CommentComposerTextEditor"
        controller.attachIfNeeded(textView)
        return textView
    }

    func updateUIView(_ uiView: UITextView, context: Context) {
        controller.attachIfNeeded(uiView)
    }

    func makeCoordinator() -> Coordinator { Coordinator(controller: controller) }

    final class Coordinator: NSObject, UITextViewDelegate {
        let controller: CommentFormatController
        init(controller: CommentFormatController) { self.controller = controller }

        func textViewDidChange(_ textView: UITextView) {
            controller.userChangedText(textView.text)
        }
    }
}

/// The shared composer sheet for writing a comment — used both for a brand new
/// comment on the post and for replying to a thread (issues #266, #289, #290).
/// It always shows the character counter, and submitting dismisses the sheet
/// (and thus the keyboard) immediately, so tapping the confirm button repeatedly
/// can't post the same comment twice (issue #291). A formatting toolbar styles
/// the current selection with bold/italic/size (issue #318).
struct CommentComposerView: View {
      @Environment(\.dismiss) var dismiss

      /// The sheet's title — e.g. "Add Comment" or "Post Reply".
      let title: String

      /// The action to perform when the confirm button is tapped, carrying the
      /// text and any inline formatting spans (issue #318).
      let onSubmit: (String, [CommentFormatSpan]?) -> Void

      @StateObject private var controller = CommentFormatController()

      var body: some View {
          NavigationView {
              Form {
                  Section {
                      // Inline formatting toolbar: styles the current selection.
                      HStack(spacing: 20) {
                          Button { controller.toggleBold() } label: {
                              Image(systemName: "bold")
                          }
                          .accessibilityLabel("Bold selection")
                          Button { controller.toggleItalic() } label: {
                              Image(systemName: "italic")
                          }
                          .accessibilityLabel("Italic selection")
                          Menu {
                              ForEach(["small", "normal", "large", "xlarge"], id: \.self) { size in
                                  Button(size.capitalized) { controller.setSize(size) }
                              }
                          } label: {
                              Label("Size", systemImage: "textformat.size")
                          }
                          .accessibilityLabel("Text size for selection")
                          Spacer()
                      }
                      .buttonStyle(.borderless)
                      .font(.headline)

                      FormattedTextEditor(controller: controller)
                          .frame(minHeight: 150)
                      Text("Select text, then tap Bold, Italic, or Size to format it.")
                          .font(.caption)
                          .foregroundColor(.secondary)
                      CharacterCounter(text: controller.text, max: GVOAppConstants.maxCommentLength)
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
                          onSubmit(controller.text, controller.spans)
                          dismiss()
                      }
                      .disabled(!controller.isSubmittable)
                      .accessibilityIdentifier("PostCommentButton")
                  }
              }
          }
      }
  }
