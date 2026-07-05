import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router-dom'
import { vi, beforeEach } from 'vitest'
import VerifyEmailPage from './VerifyEmailPage'

vi.mock('../api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    apiClient: { verifyEmail: vi.fn(), resendVerificationEmail: vi.fn() },
  }
})

import { apiClient } from '../api/client'
const mockVerifyEmail = vi.mocked(apiClient.verifyEmail)
const mockResend = vi.mocked(apiClient.resendVerificationEmail)

const VALID_TOKEN = 'a'.repeat(43)

function renderVerifyEmailPage(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockVerifyEmail.mockReset()
  mockResend.mockReset()
})

test('verifies automatically and shows success with a login link', async () => {
  mockVerifyEmail.mockResolvedValueOnce({ message: 'Email verified' })
  renderVerifyEmailPage(`/verify-email?token=${VALID_TOKEN}`)

  expect(await screen.findByText(/has been verified/)).toBeInTheDocument()
  expect(mockVerifyEmail).toHaveBeenCalledWith({ verification_token: VALID_TOKEN })
  expect(mockVerifyEmail).toHaveBeenCalledTimes(1)

  await userEvent.click(screen.getByRole('button', { name: 'Go to Login' }))
  expect(screen.getByText('Login page')).toBeInTheDocument()
})

test('navigating to a different token while mounted verifies the new token', async () => {
  const SECOND_TOKEN = 'b'.repeat(43)
  mockVerifyEmail.mockRejectedValueOnce({ message: 'Invalid or expired verification token' })
  mockVerifyEmail.mockResolvedValueOnce({ message: 'Email verified' })

  // React Router reuses the mounted component when only the search param
  // changes, so the single-use guard must be keyed by token, not a boolean.
  function NavigateToSecondToken() {
    const navigate = useNavigate()
    return (
      <button onClick={() => navigate(`/verify-email?token=${SECOND_TOKEN}`)}>
        Open second link
      </button>
    )
  }

  render(
    <MemoryRouter initialEntries={[`/verify-email?token=${VALID_TOKEN}`]}>
      <Routes>
        <Route
          path="/verify-email"
          element={
            <>
              <VerifyEmailPage />
              <NavigateToSecondToken />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  )

  await screen.findByRole('alert')
  await userEvent.click(screen.getByRole('button', { name: 'Open second link' }))

  expect(await screen.findByText(/has been verified/)).toBeInTheDocument()
  expect(mockVerifyEmail).toHaveBeenCalledTimes(2)
  expect(mockVerifyEmail).toHaveBeenLastCalledWith({ verification_token: SECOND_TOKEN })
})

test('shows an explanation when the token is missing from the URL', () => {
  renderVerifyEmailPage('/verify-email')
  expect(screen.getByText(/missing its token/)).toBeInTheDocument()
  expect(mockVerifyEmail).not.toHaveBeenCalled()
})

test('shows the error and a resend form when verification fails', async () => {
  mockVerifyEmail.mockRejectedValueOnce({ message: 'Invalid or expired verification token' })
  renderVerifyEmailPage(`/verify-email?token=${VALID_TOKEN}`)

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Invalid or expired verification token',
  )
  expect(screen.getByLabelText('Username or Email')).toBeInTheDocument()
})

test('resend form requests a new verification email', async () => {
  mockVerifyEmail.mockRejectedValueOnce({ message: 'Invalid or expired verification token' })
  mockResend.mockResolvedValueOnce({ message: 'Verification email sent' })
  renderVerifyEmailPage(`/verify-email?token=${VALID_TOKEN}`)

  await screen.findByRole('alert')
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada@example.com')
  await userEvent.click(screen.getByRole('button', { name: 'Resend Verification Email' }))

  expect(await screen.findByRole('status')).toHaveTextContent(/on its way/)
  expect(mockResend).toHaveBeenCalledWith({ username_or_email: 'ada@example.com' })
})

test('resend failure surfaces the backend error', async () => {
  mockVerifyEmail.mockRejectedValueOnce({ message: 'Invalid or expired verification token' })
  mockResend.mockRejectedValueOnce({ message: 'Email already verified' })
  renderVerifyEmailPage(`/verify-email?token=${VALID_TOKEN}`)

  await screen.findByRole('alert')
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada@example.com')
  await userEvent.click(screen.getByRole('button', { name: 'Resend Verification Email' }))

  expect(await screen.findByRole('status')).toHaveTextContent('Email already verified')
})
