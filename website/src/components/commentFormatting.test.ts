import { test, expect } from 'vitest'
import {
  applyStyleToRange,
  attrsToSpans,
  emptyAttrs,
  reconcileAttrs,
  spansForTrimmedComment,
  toggleRange,
} from './commentFormatting'

test('emptyAttrs makes one unstyled entry per character', () => {
  const attrs = emptyAttrs(3)
  expect(attrs).toHaveLength(3)
  expect(attrs.every((a) => !a.bold && !a.italic && a.size === 'normal')).toBe(true)
})

test('applyStyleToRange only styles the given range', () => {
  const attrs = applyStyleToRange(emptyAttrs(5), 1, 3, { bold: true })
  expect(attrs.map((a) => a.bold)).toEqual([false, true, true, false, false])
})

test('toggleRange turns a style on, then off when the whole range has it', () => {
  const on = toggleRange(emptyAttrs(4), 0, 4, 'bold')
  expect(on.every((a) => a.bold)).toBe(true)
  const off = toggleRange(on, 0, 4, 'bold')
  expect(off.every((a) => !a.bold)).toBe(true)
})

test('toggleRange turns on when only part of the range has the style', () => {
  const partial = applyStyleToRange(emptyAttrs(4), 0, 2, { italic: true })
  const toggled = toggleRange(partial, 0, 4, 'italic')
  expect(toggled.every((a) => a.italic)).toBe(true)
})

test('attrsToSpans compresses contiguous equal runs and drops plain text', () => {
  let attrs = emptyAttrs(6)
  attrs = applyStyleToRange(attrs, 0, 2, { bold: true })
  attrs = applyStyleToRange(attrs, 4, 6, { size: 'large' })
  expect(attrsToSpans(attrs)).toEqual([
    { start: 0, end: 2, bold: true, italic: false, size: 'normal' },
    { start: 4, end: 6, bold: false, italic: false, size: 'large' },
  ])
})

test('reconcileAttrs keeps styling when text is inserted in the middle', () => {
  // "ab" with both chars bold; type "X" between them -> "aXb".
  const attrs = applyStyleToRange(emptyAttrs(2), 0, 2, { bold: true })
  const next = reconcileAttrs(attrs, 'ab', 'aXb')
  expect(next.map((a) => a.bold)).toEqual([true, false, true])
})

test('reconcileAttrs drops styling for deleted characters', () => {
  const attrs = applyStyleToRange(emptyAttrs(3), 0, 3, { bold: true })
  const next = reconcileAttrs(attrs, 'abc', 'ac')
  expect(next).toHaveLength(2)
  expect(next.every((a) => a.bold)).toBe(true)
})

test('spansForTrimmedComment aligns offsets to the trimmed text', () => {
  // Two leading spaces, then "hi"; bold the "hi".
  const raw = '  hi'
  const attrs = applyStyleToRange(emptyAttrs(raw.length), 2, 4, { bold: true })
  expect(spansForTrimmedComment(raw, attrs)).toEqual([
    { start: 0, end: 2, bold: true, italic: false, size: 'normal' },
  ])
})

test('spansForTrimmedComment returns undefined when nothing is styled', () => {
  expect(spansForTrimmedComment('plain', emptyAttrs(5))).toBeUndefined()
})
