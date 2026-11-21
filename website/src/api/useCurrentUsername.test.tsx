import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test } from 'vitest'
import { updateStoredUsername } from './session'
import { useCurrentUsername } from './useCurrentUsername'

function ShowUsername() {
  return <span>{useCurrentUsername() ?? 'nobody'}</span>
}

beforeEach(() => {
  sessionStorage.setItem('session_token', 'token')
  sessionStorage.setItem('username', 'before_rename')
})

afterEach(() => {
  sessionStorage.clear()
})

test('a view that already rendered follows a rename (#594)', () => {
  render(<ShowUsername />)
  expect(screen.getByText('before_rename')).toBeInTheDocument()

  act(() => updateStoredUsername('after_rename'))

  expect(screen.getByText('after_rename')).toBeInTheDocument()
})
