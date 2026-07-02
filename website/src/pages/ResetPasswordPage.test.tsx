import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, afterEach } from 'vitest'
import ResetPasswordPage from './ResetPasswordPage'

vi.mock('../api/client', () => ({
  apiClient: { resetPassword: vi.fn(), login: vi.fn() },
}))

import { apiClient } from '../api/client'
const mockResetPassword = vi.mocked(apiClient.resetPassword)
const mockLogin = vi.mocked(apiClient.login)

let mockSetItem: ReturnType<typeof vi.fn>

function renderPage(usernameOrEmail = 'ada', resetToken = 'rt-tok') {
  return render(
    <MemoryRouter
      initialEntries={[{ pathname: '/reset-password', state: { usernameOrEmail, resetToken } }]}
    >
      <Routes>
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/verify-reset" element={<div>Verify reset page</div>} />
        <Route path="/home" element={<div>Home page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockResetPassword.mockReset()
  mockLogin.mockReset()
  mockSetItem = vi.fn()
  vi.stubGlobal('localStorage', {
    setItem: mockSetItem,
    getItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('renders the form with all fields', () => {
  renderPage()
  expect(screen.getByRole('heading', { name: 'Set New Password' })).toBeInTheDocument()
  expect(screen.getByLabelText('Username')).toBeInTheDocument()
  expect(screen.getByLabelText('Email')).toBeInTheDocument()
  expect(screen.getByLabelText('New Password')).toBeInTheDocument()
  expect(screen.getByLabelText('Confirm Password')).toBeInTheDocument()
})

test('pre-fills username when usernameOrEmail has no @', () => {
  renderPage('ada')
  expect(screen.getByLabelText<HTMLInputElement>('Username').value).toBe('ada')
  expect(screen.getByLabelText<HTMLInputElement>('Email').value).toBe('')
})

test('pre-fills email when usernameOrEmail contains @', () => {
  renderPage('ada@example.com')
  expect(screen.getByLabelText<HTMLInputElement>('Email').value).toBe('ada@example.com')
  expect(screen.getByLabelText<HTMLInputElement>('Username').value).toBe('')
})

test('submit button is disabled when fields are incomplete', () => {
  renderPage('ada')
  expect(screen.getByRole('button', { name: 'Reset Password and Login' })).toBeDisabled()
})

test('submit button is enabled when all fields are filled', async () => {
  renderPage('ada')
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('New Password'), 'NewStrongPass1-')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'NewStrongPass1-')
  expect(screen.getByRole('button', { name: 'Reset Password and Login' })).toBeEnabled()
})

test('submit button stays disabled when passwords do not match', async () => {
  renderPage('ada')
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('New Password'), 'NewStrongPass1-')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'different')
  expect(screen.getByRole('button', { name: 'Reset Password and Login' })).toBeDisabled()
})

test('shows mismatch warning when passwords differ', async () => {
  renderPage('ada')
  await userEvent.type(screen.getByLabelText('New Password'), 'abc')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'xyz')
  expect(screen.getByText('Passwords do not match.')).toBeInTheDocument()
})

test('password hints appear when new password is typed', async () => {
  renderPage('ada')
  await userEvent.type(screen.getByLabelText('New Password'), 'pass')
  expect(screen.getByText('At least 8 characters')).toBeInTheDocument()
  expect(screen.getByText('At least one number')).toBeInTheDocument()
  expect(screen.getByText('At least one lowercase letter')).toBeInTheDocument()
  expect(screen.getByText('At least one uppercase letter')).toBeInTheDocument()
  expect(screen.getByText('At least one dash (-)')).toBeInTheDocument()
  expect(screen.getByText('Adding other special characters (like !) is suggested')).toBeInTheDocument()
  expect(screen.getByText('No spaces')).toBeInTheDocument()
})

test('submit button stays disabled when password fails requirements', async () => {
  renderPage('ada')
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  // weak password: no uppercase/number/special
  await userEvent.type(screen.getByLabelText('New Password'), 'lowercase')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'lowercase')
  expect(screen.getByRole('button', { name: 'Reset Password and Login' })).toBeDisabled()
})

test('navigates to /home on successful reset and login', async () => {
  mockResetPassword.mockResolvedValueOnce({ message: 'Password reset successfully' })
  mockLogin.mockResolvedValueOnce({
    session_management_token: 'tok',
    user_id: 'uid',
    username: 'ada',
  })
  renderPage('ada')
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('New Password'), 'NewStrongPass1-')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'NewStrongPass1-')
  await userEvent.click(screen.getByRole('button', { name: 'Reset Password and Login' }))
  expect(await screen.findByText('Home page')).toBeInTheDocument()
})

test('stores session token and user_id in localStorage on success', async () => {
  mockResetPassword.mockResolvedValueOnce({ message: 'Password reset successfully' })
  mockLogin.mockResolvedValueOnce({
    session_management_token: 'my-token',
    user_id: 'uuid-xyz',
    username: 'ada',
  })
  renderPage('ada')
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('New Password'), 'NewStrongPass1-')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'NewStrongPass1-')
  await userEvent.click(screen.getByRole('button', { name: 'Reset Password and Login' }))
  await screen.findByText('Home page')
  expect(mockSetItem).toHaveBeenCalledWith('session_token', 'my-token')
  expect(mockSetItem).toHaveBeenCalledWith('user_id', 'uuid-xyz')
})

test('shows error banner when reset fails', async () => {
  mockResetPassword.mockRejectedValueOnce({ message: 'Invalid reset token' })
  renderPage('ada')
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('New Password'), 'NewStrongPass1-')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'NewStrongPass1-')
  await userEvent.click(screen.getByRole('button', { name: 'Reset Password and Login' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid reset token')
})

test('shows error banner when auto-login fails after reset', async () => {
  mockResetPassword.mockResolvedValueOnce({ message: 'Password reset successfully' })
  mockLogin.mockRejectedValueOnce({ message: 'Invalid username or password' })
  renderPage('ada')
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('New Password'), 'NewStrongPass1-')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'NewStrongPass1-')
  await userEvent.click(screen.getByRole('button', { name: 'Reset Password and Login' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password')
})

test('error banner can be dismissed', async () => {
  mockResetPassword.mockRejectedValueOnce({ message: 'Invalid reset token' })
  renderPage('ada')
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('New Password'), 'NewStrongPass1-')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'NewStrongPass1-')
  await userEvent.click(screen.getByRole('button', { name: 'Reset Password and Login' }))
  await screen.findByRole('alert')
  await userEvent.click(screen.getByRole('button', { name: 'Dismiss error' }))
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('Back button navigates to /verify-reset', async () => {
  renderPage('ada', 'rt-tok')
  await userEvent.click(screen.getByRole('button', { name: 'Back to verify reset' }))
  expect(screen.getByText('Verify reset page')).toBeInTheDocument()
})

test('redirects to /request-reset when resetToken is missing from state', () => {
  render(
    <MemoryRouter initialEntries={['/reset-password']}>
      <Routes>
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/request-reset" element={<div>Request reset page</div>} />
      </Routes>
    </MemoryRouter>,
  )
  expect(screen.getByText('Request reset page')).toBeInTheDocument()
})
