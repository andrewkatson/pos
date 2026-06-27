import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, afterEach } from 'vitest'
import LoginPage from './LoginPage'

vi.mock('../api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return { ...actual, apiClient: { login: vi.fn() } }
})

import { apiClient } from '../api/client'
const mockLogin = vi.mocked(apiClient.login)

function makeStorageMock() {
  return { setItem: vi.fn(), getItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn() }
}

let localStorageMock: ReturnType<typeof makeStorageMock>
let sessionStorageMock: ReturnType<typeof makeStorageMock>

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
  localStorageMock = makeStorageMock()
  sessionStorageMock = makeStorageMock()
  vi.stubGlobal('localStorage', localStorageMock)
  vi.stubGlobal('sessionStorage', sessionStorageMock)
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

test('stores the session in sessionStorage (ephemeral) when remember me is off', async () => {
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
  // Without remember me the session must not persist across browser restarts.
  expect(sessionStorageMock.setItem).toHaveBeenCalledWith('session_token', 'my-token')
  expect(sessionStorageMock.setItem).toHaveBeenCalledWith('user_id', 'uuid-xyz')
  expect(localStorageMock.setItem).not.toHaveBeenCalledWith('session_token', 'my-token')
})

test('persists the session and remember-me tokens in localStorage when remember me is checked', async () => {
  mockLogin.mockResolvedValueOnce({
    session_management_token: 'tok',
    user_id: 'uuid-xyz',
    username: 'ada',
    series_identifier: 'series-1',
    login_cookie_token: 'cookie-1',
  })
  renderLoginPage()
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  await userEvent.type(screen.getByLabelText('Password'), 'pass')
  await userEvent.click(screen.getByLabelText('Remember me'))
  await userEvent.click(screen.getByRole('button', { name: 'Login' }))
  await screen.findByText('Home')
  // Remembered sessions survive browser restarts, so they live in localStorage.
  expect(localStorageMock.setItem).toHaveBeenCalledWith('session_token', 'tok')
  expect(localStorageMock.setItem).toHaveBeenCalledWith('user_id', 'uuid-xyz')
  expect(sessionStorageMock.setItem).not.toHaveBeenCalledWith('session_token', expect.anything())
  expect(localStorageMock.setItem).toHaveBeenCalledWith('series_identifier', 'series-1')
  expect(localStorageMock.setItem).toHaveBeenCalledWith('login_cookie_token', 'cookie-1')
})

test('does not persist remember-me tokens when remember me is unchecked', async () => {
  mockLogin.mockResolvedValueOnce({
    session_management_token: 'tok',
    user_id: 'uuid-xyz',
    username: 'ada',
    series_identifier: 'series-1',
    login_cookie_token: 'cookie-1',
  })
  renderLoginPage()
  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  await userEvent.type(screen.getByLabelText('Password'), 'pass')
  await userEvent.click(screen.getByRole('button', { name: 'Login' }))
  await screen.findByText('Home')
  expect(localStorageMock.setItem).not.toHaveBeenCalledWith('series_identifier', expect.anything())
  expect(localStorageMock.setItem).not.toHaveBeenCalledWith('login_cookie_token', expect.anything())
})

test('Forgot Password link navigates to /request-reset', async () => {
  renderLoginPage()
  await userEvent.click(screen.getByRole('button', { name: 'Forgot Password?' }))
  expect(screen.getByText('Reset page')).toBeInTheDocument()
})

test('shows suspension message when login fails with account_banned', async () => {
  const { ACCOUNT_BANNED, ACCOUNT_SUSPENDED_MESSAGE, ApiError } = await import('../api/client')
  mockLogin.mockRejectedValue(new ApiError(403, ACCOUNT_BANNED))
  renderLoginPage()

  await userEvent.type(screen.getByLabelText('Username or Email'), 'ada')
  await userEvent.type(screen.getByLabelText('Password'), 'pass')
  await userEvent.click(screen.getByRole('button', { name: 'Login' }))

  expect(await screen.findByText(ACCOUNT_SUSPENDED_MESSAGE)).toBeInTheDocument()
})

test('shows suspension message when redirected with the suspended flag', async () => {
  const { ACCOUNT_SUSPENDED_MESSAGE } = await import('../api/client')
  render(
    <MemoryRouter initialEntries={['/login?suspended=1']}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    </MemoryRouter>,
  )

  expect(screen.getByText(ACCOUNT_SUSPENDED_MESSAGE)).toBeInTheDocument()
})
