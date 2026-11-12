
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
    /// The character limit the counter and Post button enforce — a comment's
    /// by default, a caption's when editing one (issue #462).
    let maxLength: Int

    /// Starts empty for a new comment, or from an existing comment's text and
    /// formatting when editing it (issue #462).
    init(text: String = "", spans: [CommentFormatSpan]? = nil, maxLength: Int = GVOAppConstants.maxCommentLength) {
        self.text = text
        self.maxLength = maxLength
        var styles = Array(repeating: CharStyle(), count: (text as NSString).length)
        for span in spans ?? [] {
            let lo = max(0, span.start), hi = min(styles.count, span.end)
            guard lo < hi else { continue }
            for i in lo..<hi {
                if span.bold { styles[i].bold = true }
                if span.italic { styles[i].italic = true }
                styles[i].size = span.size
            }
        }
        self.styles = styles
    }

    var isSubmittable: Bool {
        !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && isWithinLength(text, max: maxLength)
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
    /// style array across the edit. It deliberately does NOT re-render the
    /// attributed text: re-assigning `attributedText` on every keystroke
    /// disrupts typing (and hangs UI-test text entry). The text view keeps the
    /// runs it already has, and toolbar actions re-render on demand.
    func userChangedText(_ newText: String) {
        reconcile(to: newText)
        text = newText
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
            // Ignore callbacks where the plain text hasn't actually changed —
            // e.g. a programmatic `attributedText` assignment from a toolbar
            // re-render — so there's no re-entrant update / feedback cycle.
            guard textView.text != controller.text else { return }
            controller.userChangedText(textView.text)
        }
    }
}

/// The shared composer sheet for writing a comment — used for a brand new
/// comment on the post, for replying to a thread (issues #266, #289, #290), and,
/// prefilled, for editing a comment or a caption (issue #462). It always shows
/// the character counter, and submitting dismisses the sheet (and thus the
/// keyboard) immediately, so tapping the confirm button repeatedly can't post
/// the same comment twice (issue #291). A formatting toolbar styles the current
/// selection with bold/italic/size (issue #318).
struct CommentComposerView: View {
      @Environment(\.dismiss) var dismiss

      /// The sheet's title — e.g. "Add Comment" or "Post Reply".
      let title: String

      /// The confirm button's label — "Post", or "Save" for an edit.
      let confirmTitle: String

      /// The bold/italic/size toolbar (issue #318). Off when editing a caption,
      /// which is styled as a whole rather than inline.
      let showsFormatting: Bool

      /// The audience picker (issue #445). Off for an edit, which keeps the
      /// audience the comment was shared with.
      let showsAudience: Bool

      /// The action to perform when the confirm button is tapped, carrying the
      /// text, any inline formatting spans (issue #318), and the chosen audience
      /// (issue #445).
      let onSubmit: (String, [CommentFormatSpan]?, PostAudience) -> Void

      @StateObject private var controller: CommentFormatController

      init(
          title: String,
          confirmTitle: String = "Post",
          initialText: String = "",
          initialFormatting: [CommentFormatSpan]? = nil,
          showsFormatting: Bool = true,
          showsAudience: Bool = true,
          maxLength: Int = GVOAppConstants.maxCommentLength,
          onSubmit: @escaping (String, [CommentFormatSpan]?, PostAudience) -> Void
      ) {
          self.title = title
          self.confirmTitle = confirmTitle
          self.showsFormatting = showsFormatting
          self.showsAudience = showsAudience
          self.onSubmit = onSubmit
          _controller = StateObject(wrappedValue: CommentFormatController(
              text: initialText, spans: initialFormatting, maxLength: maxLength))
      }

      /// Who may see the comment being written (issue #445); defaults to public.
      @State private var selectedAudience: PostAudience = .public

      var body: some View {
          NavigationView {
              Form {
                  Section {
                      FormattedTextEditor(controller: controller)
                          .frame(minHeight: 150)

                      // The formatting toolbar sits below the editor so the
                      // system's text-selection callout (Cut/Copy/Paste), which
                      // pops up above the highlighted text, doesn't cover the
                      // Bold/Italic/Size controls (issue #425).
                      if showsFormatting {
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

                          Text("Select text, then tap Bold, Italic, or Size to format it.")
                              .font(.caption)
                              .foregroundColor(.secondary)
                      }
                      CharacterCounter(text: controller.text, max: controller.maxLength)
                  }

                  // Who may see this comment (issue #445), mirroring the post
                  // audience picker in NewPostView.
                  if showsAudience {
                      Section {
                          Picker("Who can see this?", selection: $selectedAudience) {
                              ForEach(PostAudience.allCases) { audience in
                                  Text(audience.displayName).tag(audience)
                              }
                          }
                          .accessibilityIdentifier("CommentAudiencePicker")
                      }
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
                      Button(confirmTitle) {
                          onSubmit(controller.text, showsFormatting ? controller.spans : nil, selectedAudience)
                          dismiss()
                      }
                      .disabled(!controller.isSubmittable)
                      .accessibilityIdentifier("PostCommentButton")
                  }
              }
          }
      }
  }

extension CommentComposerView {
    /// The composer set up for editing a post's caption (issue #462): prefilled,
    /// with the caption's length limit, and without the inline formatting
    /// toolbar (a caption is styled whole) or the audience picker.
    static func captionEditor(caption: String, onSave: @escaping (String) -> Void) -> CommentComposerView {
        CommentComposerView(
            title: "Edit Caption",
            confirmTitle: "Save",
            initialText: caption,
            showsFormatting: false,
            showsAudience: false,
            maxLength: GVOAppConstants.maxCaptionLength
        ) { text, _, _ in
            onSave(text)
        }
    }
}
