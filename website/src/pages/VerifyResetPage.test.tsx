import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach } from 'vitest'
import VerifyResetPage from './VerifyResetPage'

vi.mock('../api/client', () => ({
  apiClient: { verifyReset: vi.fn() },
}))

import { apiClient } from '../api/client'
const mockVerifyReset = vi.mocked(apiClient.verifyReset)

function renderPage(usernameOrEmail = 'ada') {
  return render(
    <MemoryRouter
      initialEntries={[{ pathname: '/verify-reset', state: { usernameOrEmail } }]}
    >
      <Routes>
        <Route path="/verify-reset" element={<VerifyResetPage />} />
        <Route path="/request-reset" element={<div>Request reset page</div>} />
        <Route path="/reset-password" element={<div>Reset password page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockVerifyReset.mockReset()
})

test('renders the form with the target address', () => {
  renderPage('ada@example.com')
  expect(screen.getByRole('heading', { name: 'Enter Verification Token' })).toBeInTheDocument()
  expect(screen.getByLabelText('Verification Token')).toBeInTheDocument()
  expect(screen.getByText(/ada@example.com/)).toBeInTheDocument()
})

test('Verify button is disabled when token field is empty', () => {
  renderPage()
  expect(screen.getByRole('button', { name: 'Verify' })).toBeDisabled()
})

test('Verify button is enabled when token field has input', async () => {
  renderPage()
  await userEvent.type(screen.getByLabelText('Verification Token'), 'abc123')
  expect(screen.getByRole('button', { name: 'Verify' })).toBeEnabled()
})

test('navigates to /reset-password on successful verification', async () => {
  mockVerifyReset.mockResolvedValueOnce({ message: 'Verification successful', reset_token: 'rt-tok' })
  renderPage()
  await userEvent.type(screen.getByLabelText('Verification Token'), 'abc123')
  await userEvent.click(screen.getByRole('button', { name: 'Verify' }))
  expect(await screen.findByText('Reset password page')).toBeInTheDocument()
})

test('shows error banner on invalid token', async () => {
  mockVerifyReset.mockRejectedValueOnce({ message: 'Invalid or expired verification token' })
  renderPage()
  await userEvent.type(screen.getByLabelText('Verification Token'), 'bad')
  await userEvent.click(screen.getByRole('button', { name: 'Verify' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid or expired verification token')
})

test('error banner can be dismissed', async () => {
  mockVerifyReset.mockRejectedValueOnce({ message: 'Invalid or expired verification token' })
  renderPage()
  await userEvent.type(screen.getByLabelText('Verification Token'), 'bad')
  await userEvent.click(screen.getByRole('button', { name: 'Verify' }))
  await screen.findByRole('alert')
  await userEvent.click(screen.getByRole('button', { name: 'Dismiss error' }))
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('error clears when retry succeeds', async () => {
  mockVerifyReset
    .mockRejectedValueOnce({ message: 'Invalid or expired verification token' })
    .mockResolvedValueOnce({ message: 'Verification successful', reset_token: 'rt-tok' })
  renderPage()
  await userEvent.type(screen.getByLabelText('Verification Token'), 'bad')
  await userEvent.click(screen.getByRole('button', { name: 'Verify' }))
  await screen.findByRole('alert')
  await userEvent.click(screen.getByRole('button', { name: 'Verify' }))
  expect(await screen.findByText('Reset password page')).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('Back button navigates to /request-reset', async () => {
  renderPage()
  await userEvent.click(screen.getByRole('button', { name: 'Back to request reset' }))
  expect(screen.getByText('Request reset page')).toBeInTheDocument()
})

test('redirects to /request-reset when usernameOrEmail is missing from state', () => {
  render(
    <MemoryRouter initialEntries={['/verify-reset']}>
      <Routes>
        <Route path="/verify-reset" element={<VerifyResetPage />} />
        <Route path="/request-reset" element={<div>Request reset page</div>} />
      </Routes>
    </MemoryRouter>,
  )
  expect(screen.getByText('Request reset page')).toBeInTheDocument()
})
