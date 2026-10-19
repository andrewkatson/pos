import { useRef, useState } from 'react'
import type { CommentFormatSpan, PostAudience, TextSize } from '../api/types'
import { isWithinLimit, MAX_COMMENT_LENGTH } from '../auth/requirements'
import CharacterCounter from './CharacterCounter'
import FormattedText from './FormattedText'
import { TEXT_SIZE_OPTIONS } from './textFormatting'
import {
  applyStyleToRange,
  attrsFromSpans,
  attrsToSpans,
  reconcileAttrs,
  spansForTrimmedComment,
  toggleRange,
  type CharAttrs,
} from './commentFormatting'

// Who may see a comment (issue #445), mirroring the post audience picker. The
// values match the backend/PostAudience tiers.
const COMMENT_AUDIENCE_OPTIONS: { value: PostAudience; label: string }[] = [
  { value: 'public', label: 'Public — anyone can see this comment' },
  { value: 'following', label: 'People I follow' },
  { value: 'friends', label: 'Friends and family' },
  { value: 'family', label: 'Family only' },
]

interface CommentComposerDialogProps {
  /** The dialog heading, e.g. "Add a comment" or "Edit caption". */
  title: string
  /** The confirm button's label, e.g. "Post", "Send" or "Save". */
  submitLabel: string
  /** Prefilled text, for an edit (issue #462). Empty for a new comment. */
  initialText?: string
  /** Prefilled inline formatting over `initialText`, for a comment edit. */
  initialFormatting?: CommentFormatSpan[] | null
  /** The bold/italic/size toolbar (issue #318). Comments have it; a caption
   * is styled as a whole from the composer instead, so its edit turns it off. */
  allowFormatting?: boolean
  /** The audience picker (issue #445). An edit keeps the audience it was
   * shared with, so it turns the picker off. */
  showAudience?: boolean
  maxLength?: number
  /** Accessible name of the text area. */
  textLabel?: string
  /** Trim surrounding whitespace on submit — right for new text. An edit
   * (issue #462) turns it off, so opening an item and pressing Save never
   * changes text the mobile composers saved with surrounding spaces, and a
   * formatting-only edit stays formatting-only. */
  trimOnSubmit?: boolean
  onCancel: () => void
  /** `text` is trimmed unless `trimOnSubmit` is off; `formatting` is aligned
   * to it and undefined when the text is plain. */
  onSubmit: (text: string, formatting: CommentFormatSpan[] | undefined, audience: PostAudience) => void
}

/**
 * The comment composer dialog: a new post comment, a thread reply, and — with
 * prefilled text — editing a comment or a post caption (issue #462), so every
 * way of writing text under a post shows the same character-limit popup
 * (issues #266, #289, #290). Mount it only while open, so each open starts
 * from its initial text.
 */
export default function CommentComposerDialog({
  title,
  submitLabel,
  initialText = '',
  initialFormatting = null,
  allowFormatting = true,
  showAudience = true,
  maxLength = MAX_COMMENT_LENGTH,
  textLabel = 'Comment text',
  trimOnSubmit = true,
  onCancel,
  onSubmit,
}: CommentComposerDialogProps) {
  const [text, setText] = useState(initialText)
  // Inline formatting for the text being composed (issue #318), tracked as a
  // per-character attribute array aligned to `text`. The textarea ref lets the
  // toolbar read the current selection to style.
  const [attrs, setAttrs] = useState<CharAttrs>(() => attrsFromSpans(initialText, initialFormatting))
  // Who the comment being composed is shared with (issue #445).
  const [audience, setAudience] = useState<PostAudience>('public')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Keep the formatting attributes aligned with the text as the user edits.
  function handleTextChange(next: string) {
    setAttrs(prev => reconcileAttrs(prev, text, next))
    setText(next)
  }

  // Apply a formatting change to the textarea's current selection, then restore
  // focus and the selection so the user can keep styling the same range.
  function styleSelection(mutate: (attrs: CharAttrs, start: number, end: number) => CharAttrs) {
    const textarea = textareaRef.current
    if (!textarea) return
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    if (start === end) return
    setAttrs(prev => mutate(prev, start, end))
    requestAnimationFrame(() => {
      textarea.focus()
      textarea.setSelectionRange(start, end)
    })
  }

  // The caller closes the dialog in onSubmit, before its request is sent, so
  // repeated taps can't post the same comment twice and the keyboard/dialog
  // disappear at once (issue #291).
  function submit() {
    if (!text.trim()) return
    if (!trimOnSubmit) {
      const spans = attrsToSpans(attrs)
      onSubmit(text, allowFormatting && spans.length > 0 ? spans : undefined, audience)
      return
    }
    // Compress the per-character attributes into API spans, aligned to the
    // trimmed text we actually send (issue #318).
    onSubmit(text.trim(), allowFormatting ? spansForTrimmedComment(text, attrs) : undefined, audience)
  }

  return (
    <div className="modal-overlay">
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="composer-title">
        <h2 id="composer-title" className="modal__title">
          {title}
        </h2>
        {allowFormatting && (
          /* Inline formatting toolbar (issue #318): styles the current
             selection in the textarea below. */
          <div className="format-toolbar" role="group" aria-label="Text formatting">
            <button
              type="button"
              className="format-toolbar__btn"
              aria-label="Bold selection"
              onMouseDown={e => e.preventDefault()}
              onClick={() => styleSelection((a, s, e) => toggleRange(a, s, e, 'bold'))}
            >
              <strong>B</strong>
            </button>
            <button
              type="button"
              className="format-toolbar__btn"
              aria-label="Italic selection"
              onMouseDown={e => e.preventDefault()}
              onClick={() => styleSelection((a, s, e) => toggleRange(a, s, e, 'italic'))}
            >
              <em>I</em>
            </button>
            <label className="format-toolbar__size">
              Size
              {/* No onMouseDown preventDefault here: on a native <select> it
                  can stop the dropdown from opening. A blurred textarea still
                  retains its selection offsets, so styleSelection() reads the
                  correct range on change. The value is pinned to "" (the
                  placeholder) so re-picking the same size still fires onChange
                  and can be applied to a new selection. */}
              <select
                className="format-toolbar__select"
                aria-label="Text size for selection"
                value=""
                onChange={e => {
                  const size = e.target.value as TextSize | ''
                  if (!size) return
                  styleSelection((a, s, en) => applyStyleToRange(a, s, en, { size }))
                }}
              >
                <option value="">Size</option>
                {TEXT_SIZE_OPTIONS.map(size => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
        <textarea
          ref={textareaRef}
          className="text-area"
          rows={4}
          aria-label={textLabel}
          autoFocus
          value={text}
          onChange={e => handleTextChange(e.target.value)}
        />
        {allowFormatting && (
          <>
            <p className="format-toolbar__hint muted">
              Select text, then tap B, I, or Size to format it.
            </p>
            {text.trim() && (
              <p className="comment-preview">
                <FormattedText text={text.trim()} spans={spansForTrimmedComment(text, attrs)} />
              </p>
            )}
          </>
        )}
        {showAudience && (
          /* Who may see this comment (issue #445), mirroring the post
             audience picker. */
          <label className="composer-audience">
            Who can see this?
            <select
              className="select-input"
              aria-label="Comment audience"
              value={audience}
              onChange={e => setAudience(e.target.value as PostAudience)}
            >
              {COMMENT_AUDIENCE_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
        )}
        <CharacterCounter value={text} max={maxLength} />
        <div className="modal__actions">
          <button type="button" className="modal__cancel" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="modal__confirm"
            disabled={text.trim().length === 0 || !isWithinLimit(text, maxLength)}
            onClick={submit}
          >
            {submitLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
