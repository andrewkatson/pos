import { render } from '@testing-library/react'
import { test, expect } from 'vitest'
import FormattedText from './FormattedText'
import type { CommentFormatSpan } from '../api/types'

test('renders plain text when there are no spans', () => {
  const { container } = render(<FormattedText text="hello world" />)
  expect(container.textContent).toBe('hello world')
})

test('applies bold/italic/size classes to the styled range', () => {
  const spans: CommentFormatSpan[] = [
    { start: 0, end: 5, bold: true, italic: false, size: 'normal' },
    { start: 6, end: 11, bold: false, italic: true, size: 'large' },
  ]
  const { container } = render(<FormattedText text="hello world" spans={spans} />)

  expect(container.textContent).toBe('hello world')
  expect(container.querySelector('.fmt-bold')?.textContent).toBe('hello')
  const italic = container.querySelector('.fmt-italic')
  expect(italic?.textContent).toBe('world')
  expect(italic?.classList.contains('fmt-size--large')).toBe(true)
})

test('clamps out-of-bounds offsets to plain slices without throwing', () => {
  const spans: CommentFormatSpan[] = [{ start: 0, end: 99, bold: true, italic: false, size: 'normal' }]
  const { container } = render(<FormattedText text="hi" spans={spans} />)
  expect(container.textContent).toBe('hi')
})
