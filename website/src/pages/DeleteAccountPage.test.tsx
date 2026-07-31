import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router'
import { vi, beforeEach, test, expect } from 'vitest'
import DeleteAccountPage from './DeleteAccountPage'

vi.mock('../api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    apiClient: {
      login: vi.fn(),
      loginWithTwoFactor: vi.fn(),
      deleteAccount: vi.fn(),
      setToken: vi.fn(),
    },
  }
})

vi.mock('../api/session', () => ({
  getStoredSessionToken: vi.fn(),
  clearSession: vi.fn(),
}))

import { apiClient } from '../api/client'
import { clearSession, getStoredSessionToken } from '../api/session'

const mockLogin = vi.mocked(apiClient.login)
const mockLoginWithTwoFactor = vi.mocked(apiClient.loginWithTwoFactor)
const mockDeleteAccount = vi.mocked(apiClient.deleteAccount)
const mockClearSession = vi.mocked(clearSession)
const mockGetStoredSessionToken = vi.mocked(getStoredSessionToken)

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/delete-account']}>
      <Routes>
        <Route path="/delete-account" element={<DeleteAccountPage />} />
        <Route path="/" element={<div>Landing page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockLogin.mockReset()
  mockLoginWithTwoFactor.mockReset()
  mockDeleteAccount.mockReset().mockResolvedValue({ message: 'ok' })
  mockClearSession.mockReset()
  mockGetStoredSessionToken.mockReset().mockReturnValue(null)
})

/** Signs in with a password-only account and lands on the confirmation step. */
async function signIn() {
  mockLogin.mockResolvedValueOnce({
    session_management_token: 't',
    user_id: 'u',
  })
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  await userEvent.type(screen.getByLabelText('Password'), 'pass')
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
}

test('a visitor without a session must sign in first', () => {
  renderPage()
  expect(screen.getByLabelText('Username or Email')).toBeInTheDocument()
  expect(screen.getByLabelText('Password')).toBeInTheDocument()
  // The delete action is not reachable until identity is verified.
  expect(
    screen.queryByRole('button', { name: 'Delete my account and data' }),
  ).not.toBeInTheDocument()
})

test('signing in reveals the confirmation step, and deletion needs acknowledgement', async () => {
  renderPage()
  await signIn()

  expect(mockLogin).toHaveBeenCalledWith({
    username_or_email: 'ada',
    password: 'pass',
    remember_me: false,
  })

  const deleteButton = await screen.findByRole('button', {
    name: 'Delete my account and data',
  })
  // The button is gated on the acknowledgement checkbox.
  expect(deleteButton).toBeDisabled()

  await userEvent.click(
    screen.getByRole('checkbox', {
      name: /permanently deletes my account and data/i,
    }),
  )
  expect(deleteButton).toBeEnabled()

  await userEvent.click(deleteButton)
  expect(mockDeleteAccount).toHaveBeenCalled()
  expect(mockClearSession).toHaveBeenCalled()
  expect(
    await screen.findByText(/permanently deleted/i),
  ).toBeInTheDocument()
})

test('a restored session skips sign-in and goes straight to confirmation', async () => {
  mockGetStoredSessionToken.mockReturnValue('existing-token')
  renderPage()

  expect(screen.queryByLabelText('Password')).not.toBeInTheDocument()
  expect(
    await screen.findByRole('button', { name: 'Delete my account and data' }),
  ).toBeInTheDocument()
})

test('a two-factor account completes the challenge before confirming', async () => {
  renderPage()
  mockLogin.mockResolvedValueOnce({
    two_factor_required: true,
    challenge_token: 'c'.repeat(64),
  })
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  await userEvent.type(screen.getByLabelText('Password'), 'pass')
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }))

  mockLoginWithTwoFactor.mockResolvedValueOnce({
    session_management_token: 't',
    user_id: 'u',
  })
  await userEvent.type(screen.getByLabelText('Authenticator Code'), '123456')
  await userEvent.click(screen.getByRole('button', { name: 'Verify' }))

  expect(mockLoginWithTwoFactor).toHaveBeenCalledWith({
    challenge_token: 'c'.repeat(64),
    totp_code: '123456',
  })
  expect(
    await screen.findByRole('button', { name: 'Delete my account and data' }),
  ).toBeInTheDocument()
})

test('a failed sign-in surfaces the error and stays on the form', async () => {
  renderPage()
  mockLogin.mockRejectedValueOnce({ message: 'Login failed. Please check your credentials.' })
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  await userEvent.type(screen.getByLabelText('Password'), 'wrong')
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }))

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Login failed. Please check your credentials.',
  )
  expect(screen.getByLabelText('Password')).toBeInTheDocument()
})

test('a failed deletion surfaces the error and keeps the session', async () => {
  renderPage()
  await signIn()
  await userEvent.click(
    screen.getByRole('checkbox', {
      name: /permanently deletes my account and data/i,
    }),
  )
  mockDeleteAccount.mockRejectedValueOnce({ message: 'Something went wrong. Please try again.' })
  await userEvent.click(screen.getByRole('button', { name: 'Delete my account and data' }))

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Something went wrong. Please try again.',
  )
  // The local session is not cleared when the delete fails, so the user can retry.
  expect(mockClearSession).not.toHaveBeenCalled()
  expect(
    screen.getByRole('button', { name: 'Delete my account and data' }),
  ).toBeInTheDocument()
})

test('Cancel returns to the landing page', async () => {
  mockGetStoredSessionToken.mockReturnValue('existing-token')
  renderPage()
  await userEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
  expect(screen.getByText('Landing page')).toBeInTheDocument()
})
