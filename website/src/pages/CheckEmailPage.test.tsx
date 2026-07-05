import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach } from 'vitest'
import CheckEmailPage from './CheckEmailPage'

vi.mock('../api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return { ...actual, apiClient: { resendVerificationEmail: vi.fn() } }
})

import { apiClient } from '../api/client'
const mockResend = vi.mocked(apiClient.resendVerificationEmail)

function renderCheckEmailPage(email?: string) {
  return render(
    <MemoryRouter
      initialEntries={[{ pathname: '/check-email', state: email ? { email } : null }]}
    >
      <Routes>
        <Route path="/check-email" element={<CheckEmailPage />} />
        <Route path="/register" element={<div>Register page</div>} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockResend.mockReset()
})

test('shows the destination address and verification instructions', () => {
  renderCheckEmailPage('ada@example.com')
  expect(screen.getByRole('heading', { name: 'Check Your Email' })).toBeInTheDocument()
  expect(screen.getByText(/ada@example\.com/)).toBeInTheDocument()
})

test('redirects to register when opened without an email in state', () => {
  renderCheckEmailPage()
  expect(screen.getByText('Register page')).toBeInTheDocument()
})

test('resend button requests a new verification email', async () => {
  mockResend.mockResolvedValueOnce({ message: 'Verification email sent' })
  renderCheckEmailPage('ada@example.com')

  await userEvent.click(screen.getByRole('button', { name: 'Resend Verification Email' }))

  expect(await screen.findByRole('status')).toHaveTextContent(/on its way/)
  expect(mockResend).toHaveBeenCalledWith({ username_or_email: 'ada@example.com' })
})

test('resend failure surfaces the backend error', async () => {
  mockResend.mockRejectedValueOnce({ message: 'Email already verified' })
  renderCheckEmailPage('ada@example.com')

  await userEvent.click(screen.getByRole('button', { name: 'Resend Verification Email' }))

  expect(await screen.findByRole('status')).toHaveTextContent('Email already verified')
})

test('Go to Login navigates to the login page', async () => {
  renderCheckEmailPage('ada@example.com')
  await userEvent.click(screen.getByRole('button', { name: 'Go to Login' }))
  expect(screen.getByText('Login page')).toBeInTheDocument()
})
