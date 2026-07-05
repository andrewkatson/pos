import { render, screen,fireEvent} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, afterEach } from 'vitest'
import RegisterPage from './RegisterPage'

vi.mock('../api/client', () => ({
  apiClient: { register: vi.fn(), setToken: vi.fn() },
}))

import { apiClient } from '../api/client'
const mockRegister = vi.mocked(apiClient.register)

// Credentials that satisfy the backend patterns mirrored on the client:
// username = ^\w{10,500}$, password requires upper/lower/digit/special/no-space.
const VALID_USERNAME = 'adalovelace'
const VALID_PASSWORD = 'StrongPass1-'

function renderRegisterPage() {
  return render(
    <MemoryRouter initialEntries={['/register']}>
      <Routes>
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/" element={<div> Landing</div>}/>
        <Route path="/home" element={<div>Home</div>} />
        <Route path="/check-email" element={<div>Check Email</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

async function fillValidForm() {
  await userEvent.type(screen.getByLabelText('Username'), VALID_USERNAME)
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('Date of Birth'), '1990-01-01')
  await userEvent.type(screen.getByLabelText('Password'), VALID_PASSWORD)
  await userEvent.type(screen.getByLabelText('Confirm Password'), VALID_PASSWORD)
}

beforeEach(() => {
  mockRegister.mockReset()
  vi.stubGlobal('localStorage', { setItem: vi.fn(), getItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn() })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('renders all registration fields', () => {
  renderRegisterPage()
  expect(screen.getByRole('heading', { name: 'Create Account' })).toBeInTheDocument()
  expect(screen.getByLabelText('Username')).toBeInTheDocument()
  expect(screen.getByLabelText('Email')).toBeInTheDocument()
  expect(screen.getByLabelText('Date of Birth')).toBeInTheDocument()
  expect(screen.getByLabelText('Password')).toBeInTheDocument()
  expect(screen.getByLabelText('Confirm Password')).toBeInTheDocument()
})

test('register button is disabled when form is incomplete', () => {
  renderRegisterPage()
  expect(screen.getByRole('button', { name: 'Register' })).toBeDisabled()
})

test('username hints appear when username is typed', async () => {
  renderRegisterPage()
  await userEvent.type(screen.getByLabelText('Username'), 'ab')
  expect(screen.getByText('Between 10 and 500 characters')).toBeInTheDocument()
  expect(screen.getByText('Letters, numbers, and underscores only')).toBeInTheDocument()
})

test('username hint marks length as met when username is long enough', async () => {
  renderRegisterPage()
  await userEvent.type(screen.getByLabelText('Username'), VALID_USERNAME)
  const hints = screen.getAllByRole('listitem')
  const lengthHint = hints.find(h => h.textContent?.includes('Between 10 and 500 characters'))
  expect(lengthHint).toHaveClass('auth-hint--met')
})

test('password hints appear when password is typed', async () => {
  renderRegisterPage()
  await userEvent.type(screen.getByLabelText('Password'), 'p')
  expect(screen.getByText('At least 8 characters')).toBeInTheDocument()
  expect(screen.getByText('At least one number')).toBeInTheDocument()
  expect(screen.getByText('At least one lowercase letter')).toBeInTheDocument()
  expect(screen.getByText('At least one uppercase letter')).toBeInTheDocument()
  expect(screen.getByText('At least one dash (-)')).toBeInTheDocument()
  expect(screen.getByText('Adding other special characters (like !) is suggested')).toBeInTheDocument()
  expect(screen.getByText('No spaces')).toBeInTheDocument()
})

test('shows password mismatch warning in real time', async () => {
  renderRegisterPage()
  await userEvent.type(screen.getByLabelText('Password'), 'pass1')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'pass2')
  expect(screen.getByText('Passwords do not match.')).toBeInTheDocument()
})

test('no mismatch warning when confirm password is empty', () => {
  renderRegisterPage()
  expect(screen.queryByText('Passwords do not match.')).not.toBeInTheDocument()
})

test('register button stays disabled when password fails requirements', async () => {
  renderRegisterPage()
  await userEvent.type(screen.getByLabelText('Username'), VALID_USERNAME)
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('Date of Birth'), '1990-01-01')
  // weak password: no uppercase/number/special
  await userEvent.type(screen.getByLabelText('Password'), 'lowercase')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'lowercase')
  expect(screen.getByRole('button', { name: 'Register' })).toBeDisabled()
})

test('register button stays disabled when username is too short', async () => {
  renderRegisterPage()
  await userEvent.type(screen.getByLabelText('Username'), 'short')
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('Date of Birth'), '1990-01-01')
  await userEvent.type(screen.getByLabelText('Password'), VALID_PASSWORD)
  await userEvent.type(screen.getByLabelText('Confirm Password'), VALID_PASSWORD)
  expect(screen.getByRole('button', { name: 'Register' })).toBeDisabled()
})

test('register button stays disabled when username exceeds 500 characters', async () => {
  renderRegisterPage()
  fireEvent.change(screen.getByLabelText('Username'), {
  target: { value: 'a'.repeat(501) },
})
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('Date of Birth'), '1990-01-01')
  await userEvent.type(screen.getByLabelText('Password'), VALID_PASSWORD)
  await userEvent.type(screen.getByLabelText('Confirm Password'), VALID_PASSWORD)
  const hints = screen.getAllByRole('listitem')
  const lengthHint = hints.find(h => h.textContent?.includes('Between 10 and 500 characters'))
  expect(lengthHint).toHaveClass('auth-hint--unmet')
  expect(screen.getByRole('button', { name: 'Register' })).toBeDisabled()
})

test('register button enabled when form is fully valid', async () => {
  renderRegisterPage()
  await fillValidForm()
  expect(screen.getByRole('button', { name: 'Register' })).toBeEnabled()
})

test('clicking Register opens the privacy policy modal', async () => {
  renderRegisterPage()
  await fillValidForm()
  await userEvent.click(screen.getByRole('button', { name: 'Register' }))
  expect(screen.getByRole('dialog', { name: 'Privacy Policy' })).toBeInTheDocument()
})

test('Cancel button closes the privacy policy modal', async () => {
  renderRegisterPage()
  await fillValidForm()
  await userEvent.click(screen.getByRole('button', { name: 'Register' }))
  await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('Escape key closes the privacy policy modal', async () => {
  renderRegisterPage()
  await fillValidForm()
  await userEvent.click(screen.getByRole('button', { name: 'Register' }))
  await userEvent.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('shows error banner on failed registration', async () => {
  mockRegister.mockRejectedValueOnce({ message: 'Username already taken' })
  renderRegisterPage()
  await fillValidForm()
  await userEvent.click(screen.getByRole('button', { name: 'Register' }))
  await userEvent.click(screen.getByRole('button', { name: 'Ok' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Username already taken')
})

test('navigates to check-email on successful registration', async () => {
  mockRegister.mockResolvedValueOnce({
    session_management_token: 'tok',
    user_id: 'uuid-abc',
    username: VALID_USERNAME,
  })
  renderRegisterPage()
  await fillValidForm()
  await userEvent.click(screen.getByRole('button', { name: 'Register' }))
  await userEvent.click(screen.getByRole('button', { name: 'Ok' }))
  expect(await screen.findByText('Check Email')).toBeInTheDocument()
  // The registration session must not be kept: the account can't act until
  // the email is verified, so the user logs in afterwards instead.
  expect(vi.mocked(apiClient.setToken)).toHaveBeenCalledWith(null)
})
