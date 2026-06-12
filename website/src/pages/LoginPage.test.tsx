import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, afterEach } from 'vitest'
import LoginPage from './LoginPage'

vi.mock('../api/client', () => ({
  apiClient: { login: vi.fn() },
}))

import { apiClient } from '../api/client'
const mockLogin = vi.mocked(apiClient.login)

let mockSetItem: ReturnType<typeof vi.fn>

function renderLoginPage() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/home" element={<div>Home</div>} />
        <Route path="/request-reset" element={<div>Reset page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockLogin.mockReset()
  mockSetItem = vi.fn()
  vi.stubGlobal('localStorage', { setItem: mockSetItem, getItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn() })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('renders login form with all fields', () => {
  renderLoginPage()
  expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument()
  expect(screen.getByLabelText('Username or Email')).toBeInTheDocument()
  expect(screen.getByLabelText('Password')).toBeInTheDocument()
  expect(screen.getByLabelText('Remember me')).toBeInTheDocument()
})

test('login button is disabled when fields are empty', () => {
  renderLoginPage()
  expect(screen.getByRole('button', { name: 'Login' })).toBeDisabled()
})

test('login button is disabled when only username is filled', async () => {
  renderLoginPage()
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  expect(screen.getByRole('button', { name: 'Login' })).toBeDisabled()
})

test('login button is enabled when both fields are filled', async () => {
  renderLoginPage()
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  await userEvent.type(screen.getByLabelText('Password'), 'pass')
  expect(screen.getByRole('button', { name: 'Login' })).toBeEnabled()
})

test('shows error banner on failed login', async () => {
  mockLogin.mockRejectedValueOnce({ message: 'Invalid username or password' })
  renderLoginPage()
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  await userEvent.type(screen.getByLabelText('Password'), 'wrong')
  await userEvent.click(screen.getByRole('button', { name: 'Login' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid username or password')
})

test('error banner can be dismissed', async () => {
  mockLogin.mockRejectedValueOnce({ message: 'Bad credentials' })
  renderLoginPage()
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  await userEvent.type(screen.getByLabelText('Password'), 'wrong')
  await userEvent.click(screen.getByRole('button', { name: 'Login' }))
  await screen.findByRole('alert')
  await userEvent.click(screen.getByRole('button', { name: 'Dismiss error' }))
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('navigates to home on successful login', async () => {
  mockLogin.mockResolvedValueOnce({
    session_management_token: 'tok',
    user_id: 'uuid-abc',
    username: 'ada',
  })
  renderLoginPage()
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  await userEvent.type(screen.getByLabelText('Password'), 'pass')
  await userEvent.click(screen.getByRole('button', { name: 'Login' }))
  expect(await screen.findByText('Home')).toBeInTheDocument()
})

test('stores session token and user_id in localStorage on success', async () => {
  mockLogin.mockResolvedValueOnce({
    session_management_token: 'my-token',
    user_id: 'uuid-xyz',
    username: 'ada',
  })
  renderLoginPage()
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  await userEvent.type(screen.getByLabelText('Password'), 'pass')
  await userEvent.click(screen.getByRole('button', { name: 'Login' }))
  await screen.findByText('Home')
  expect(mockSetItem).toHaveBeenCalledWith('session_token', 'my-token')
  expect(mockSetItem).toHaveBeenCalledWith('user_id', 'uuid-xyz')
})

test('Forgot Password link navigates to /request-reset', async () => {
  renderLoginPage()
  await userEvent.click(screen.getByRole('button', { name: 'Forgot Password?' }))
  expect(screen.getByText('Reset page')).toBeInTheDocument()
})
