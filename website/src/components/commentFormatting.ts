// Editor-side model for composing inline comment formatting (issue #318).
//
// A textarea only holds plain text, so we track formatting alongside it as a
// per-character attribute array (one entry per UTF-16 code unit, matching JS
// string indexing and the backend's UTF-16 offset contract). Toolbar actions
// set attributes over the current selection; on submit we compress the array
// into the sorted, non-overlapping spans the API expects.

import type { CommentFormatSpan, TextSize } from '../api/types'

export interface CharAttr {
  bold: boolean
  italic: boolean
  size: TextSize
}

export type CharAttrs = CharAttr[]

const DEFAULT_ATTR: CharAttr = { bold: false, italic: false, size: 'normal' }

function isPlain(a: CharAttr): boolean {
  return !a.bold && !a.italic && a.size === 'normal'
}

/** A fresh attribute array of `len` unstyled characters. */
export function emptyAttrs(len: number): CharAttrs {
  return Array.from({ length: len }, () => ({ ...DEFAULT_ATTR }))
}

/**
 * Reconcile the attribute array across a single textarea edit (typing,
 * pasting, or deleting a contiguous selection) by diffing the common prefix
 * and suffix of the old and new text. Inserted characters get default
 * (unstyled) attributes; untouched characters keep theirs. The result always
 * has one entry per character in `newText`.
 */
export function reconcileAttrs(prev: CharAttrs, oldText: string, newText: string): CharAttrs {
  if (oldText === newText) return prev

  const minLen = Math.min(oldText.length, newText.length)
  let prefix = 0
  while (prefix < minLen && oldText[prefix] === newText[prefix]) prefix++

  let suffix = 0
  while (
    suffix < minLen - prefix &&
    oldText[oldText.length - 1 - suffix] === newText[newText.length - 1 - suffix]
  ) {
    suffix++
  }

  const head = prev.slice(0, prefix)
  const tail = prev.slice(oldText.length - suffix)
  const insertedLen = newText.length - suffix - prefix
  const inserted = emptyAttrs(Math.max(0, insertedLen))
  return [...head, ...inserted, ...tail]
}

/** Apply a partial attribute change to every character in [start, end). */
export function applyStyleToRange(
  attrs: CharAttrs,
  start: number,
  end: number,
  change: Partial<CharAttr>,
): CharAttrs {
  if (start >= end) return attrs
  return attrs.map((a, i) => (i >= start && i < end ? { ...a, ...change } : a))
}

/**
 * Toggle a boolean style over [start, end): if every character in the range
 * already has it on, turn it off; otherwise turn it on. Mirrors how a word
 * processor's Bold/Italic buttons behave on a selection.
 */
export function toggleRange(
  attrs: CharAttrs,
  start: number,
  end: number,
  key: 'bold' | 'italic',
): CharAttrs {
  if (start >= end) return attrs
  let allOn = true
  for (let i = start; i < end; i++) {
    if (!attrs[i][key]) {
      allOn = false
      break
    }
  }
  const change: Partial<CharAttr> = key === 'bold' ? { bold: !allOn } : { italic: !allOn }
  return applyStyleToRange(attrs, start, end, change)
}

/** Compress the attribute array into sorted, non-overlapping formatting spans,
 * dropping unstyled runs. Suitable to send straight to the API. */
export function attrsToSpans(attrs: CharAttrs): CommentFormatSpan[] {
  const spans: CommentFormatSpan[] = []
  let i = 0
  while (i < attrs.length) {
    const a = attrs[i]
    if (isPlain(a)) {
      i++
      continue
    }
    let j = i + 1
    while (
      j < attrs.length &&
      attrs[j].bold === a.bold &&
      attrs[j].italic === a.italic &&
      attrs[j].size === a.size
    ) {
      j++
    }
    spans.push({ start: i, end: j, bold: a.bold, italic: a.italic, size: a.size })
    i = j
  }
  return spans
}

/**
 * Produce the spans for a trimmed comment: comments are `.trim()`-ed before
 * sending, which shifts offsets, so we slice the attribute array to the
 * trimmed span of the raw text before compressing. Returns undefined when
 * there is no formatting, so callers can omit the field entirely.
 */
export function spansForTrimmedComment(
  rawText: string,
  attrs: CharAttrs,
): CommentFormatSpan[] | undefined {
  const leading = rawText.length - rawText.trimStart().length
  const trimmedLength = rawText.trim().length
  const sliced = attrs.slice(leading, leading + trimmedLength)
  const spans = attrsToSpans(sliced)
  return spans.length > 0 ? spans : undefined
}
