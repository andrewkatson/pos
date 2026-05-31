import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach } from 'vitest'
import RequestResetPage from './RequestResetPage'

vi.mock('../api/client', () => ({
  apiClient: { requestReset: vi.fn() },
}))

import { apiClient } from '../api/client'
const mockRequestReset = vi.mocked(apiClient.requestReset)

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/request-reset']}>
      <Routes>
        <Route path="/request-reset" element={<RequestResetPage />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockRequestReset.mockReset()
})

test('renders the form', () => {
  renderPage()
  expect(screen.getByRole('heading', { name: 'Reset Password' })).toBeInTheDocument()
  expect(screen.getByLabelText('Username or Email')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Request Reset' })).toBeDisabled()
})

test('Request Reset button is disabled when field is empty', () => {
  renderPage()
  expect(screen.getByRole('button', { name: 'Request Reset' })).toBeDisabled()
})

test('Request Reset button is enabled when field has input', async () => {
  renderPage()
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  expect(screen.getByRole('button', { name: 'Request Reset' })).toBeEnabled()
})

test('shows success message when account exists', async () => {
  mockRequestReset.mockResolvedValueOnce({ message: 'Reset email sent' })
  renderPage()
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  await userEvent.click(screen.getByRole('button', { name: 'Request Reset' }))
  expect(await screen.findByText(/if an account with that/i)).toBeInTheDocument()
})

test('shows the same success message when account does not exist (no user enumeration)', async () => {
  mockRequestReset.mockRejectedValueOnce({ message: 'No user with that username or email' })
  renderPage()
  await userEvent.type(screen.getByLabelText('Username or Email'), 'unknown')
  await userEvent.click(screen.getByRole('button', { name: 'Request Reset' }))
  expect(await screen.findByText(/if an account with that/i)).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('shows error banner for unexpected failures', async () => {
  mockRequestReset.mockRejectedValueOnce({ message: 'Network error' })
  renderPage()
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  await userEvent.click(screen.getByRole('button', { name: 'Request Reset' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Network error')
})

test('error clears when retry succeeds', async () => {
  mockRequestReset
    .mockRejectedValueOnce({ message: 'Network error' })
    .mockResolvedValueOnce({ message: 'Reset email sent' })
  renderPage()
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  await userEvent.click(screen.getByRole('button', { name: 'Request Reset' }))
  await screen.findByRole('alert')
  await userEvent.click(screen.getByRole('button', { name: 'Request Reset' }))
  expect(await screen.findByText(/if an account with that/i)).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('Back button navigates to /login', async () => {
  renderPage()
  await userEvent.click(screen.getByRole('button', { name: 'Back to login' }))
  expect(screen.getByText('Login page')).toBeInTheDocument()
})
