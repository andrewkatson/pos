import { render, screen } from '@testing-library/react'
import { test, expect } from 'vitest'
import CharacterCounter from './CharacterCounter'

test('shows count / max and stays neutral well under the limit', () => {
  const { container } = render(<CharacterCounter value={'a'.repeat(10)} max={125} />)
  expect(screen.getByText('10 / 125')).toBeInTheDocument()
  expect(container.querySelector('.char-counter--ok')).not.toBeNull()
})

test('warns (near state) once the user crosses 90% of the limit', () => {
  // 90% of 125 is 112.5, so 113 code points is the first "near" value.
  const { container } = render(<CharacterCounter value={'a'.repeat(113)} max={125} />)
  expect(container.querySelector('.char-counter--near')).not.toBeNull()
})

test('shows an over-limit message in the over state', () => {
  const { container } = render(<CharacterCounter value={'a'.repeat(130)} max={125} />)
  expect(screen.getByText('5 over the 125 character limit')).toBeInTheDocument()
  expect(container.querySelector('.char-counter--over')).not.toBeNull()
})

test('counts an emoji as a single code point, matching the backend', () => {
  // "💚" is two UTF-16 code units but one unicode code point. Five of them must
  // read as 5, not 10, so the client count matches Python len() server-side.
  render(<CharacterCounter value={'💚'.repeat(5)} max={125} />)
  expect(screen.getByText('5 / 125')).toBeInTheDocument()
})
