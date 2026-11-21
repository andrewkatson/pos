import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test } from 'vitest'
import { persistSession, updateStoredUsername } from './session'
import { useCurrentUsername, useOwnUsernames } from './useCurrentUsername'

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

function ShowOwnNames() {
  return <span>{useOwnUsernames().join(',') || 'none'}</span>
}

test('names given up this session still count as the account’s own (#594)', () => {
  render(<ShowOwnNames />)
  expect(screen.getByText('before_rename')).toBeInTheDocument()

  act(() => updateStoredUsername('after_rename'))

  // Rows fetched before the rename still carry the old name, which stays
  // reserved for this account.
  expect(screen.getByText('after_rename,before_rename')).toBeInTheDocument()
})

test('a fresh sign-in forgets the previous session’s former names', () => {
  act(() => updateStoredUsername('after_rename'))
  persistSession({ session_management_token: 't2', user_id: 'u2', username: 'someone_else' }, false)

  render(<ShowOwnNames />)
  expect(screen.getByText('someone_else')).toBeInTheDocument()
})
