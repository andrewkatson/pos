import type { ReactNode } from 'react'
import type { CommentFormatSpan } from '../api/types'
import { textSizeClass } from './textFormatting'

interface FormattedTextProps {
  /** The plain text; formatting is applied as ranges over it. */
  text: string
  /** Inline formatting spans (issue #318). Absent/empty renders plain text. */
  spans?: CommentFormatSpan[] | null
  /** Class applied to the wrapping element. */
  className?: string
}

/**
 * Renders `text` with inline bold/italic/size formatting applied over
 * character ranges (issue #318). Because formatting is structured range
 * metadata rather than markup, this only ever renders plain text nodes with
 * styling classes — there is no HTML to inject, so no XSS surface.
 *
 * Spans arrive sorted and non-overlapping (the backend enforces this); we
 * defensively clamp offsets to the string length so a malformed payload can
 * still only produce plain slices, never throw.
 */
function FormattedText({ text, spans, className }: FormattedTextProps) {
  if (!spans || spans.length === 0) {
    return <span className={className}>{text}</span>
  }

  const parts: ReactNode[] = []
  let cursor = 0

  spans.forEach((span, i) => {
    const start = Math.max(cursor, Math.min(span.start, text.length))
    const end = Math.max(start, Math.min(span.end, text.length))

    // Unformatted gap before this span.
    if (start > cursor) {
      parts.push(<span key={`plain-${i}`}>{text.slice(cursor, start)}</span>)
    }

    // Skip zero-length spans (e.g. a malformed payload clamped to start===end)
    // so we don't emit empty styled nodes; still advance the cursor.
    if (end > start) {
      const styleClass = [
        span.bold ? 'fmt-bold' : '',
        span.italic ? 'fmt-italic' : '',
        textSizeClass(span.size),
      ]
        .filter(Boolean)
        .join(' ')

      parts.push(
        <span key={`fmt-${i}`} className={styleClass || undefined}>
          {text.slice(start, end)}
        </span>,
      )
    }
    cursor = end
  })

  // Trailing unformatted text.
  if (cursor < text.length) {
    parts.push(<span key="plain-tail">{text.slice(cursor)}</span>)
  }

  return <span className={className}>{parts}</span>
}

export default FormattedText
