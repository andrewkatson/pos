import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, afterEach } from 'vitest'
import RegisterPage from './RegisterPage'

vi.mock('../api/client', () => ({
  apiClient: { register: vi.fn() },
}))

import { apiClient } from '../api/client'
const mockRegister = vi.mocked(apiClient.register)

function renderRegisterPage() {
  return render(
    <MemoryRouter initialEntries={['/register']}>
      <Routes>
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/" element={<div>Home</div>} />
      </Routes>
    </MemoryRouter>,
  )
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

test('register button enabled when form is fully valid', async () => {
  renderRegisterPage()
  await userEvent.type(screen.getByLabelText('Username'), 'ada')
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('Date of Birth'), '1990-01-01')
  await userEvent.type(screen.getByLabelText('Password'), 'pass')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'pass')
  expect(screen.getByRole('button', { name: 'Register' })).toBeEnabled()
})

test('clicking Register opens the privacy policy modal', async () => {
  renderRegisterPage()
  await userEvent.type(screen.getByLabelText('Username'), 'ada')
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('Date of Birth'), '1990-01-01')
  await userEvent.type(screen.getByLabelText('Password'), 'pass')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'pass')
  await userEvent.click(screen.getByRole('button', { name: 'Register' }))
  expect(screen.getByRole('dialog', { name: 'Privacy Policy' })).toBeInTheDocument()
})

test('Cancel button closes the privacy policy modal', async () => {
  renderRegisterPage()
  await userEvent.type(screen.getByLabelText('Username'), 'ada')
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('Date of Birth'), '1990-01-01')
  await userEvent.type(screen.getByLabelText('Password'), 'pass')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'pass')
  await userEvent.click(screen.getByRole('button', { name: 'Register' }))
  await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('Escape key closes the privacy policy modal', async () => {
  renderRegisterPage()
  await userEvent.type(screen.getByLabelText('Username'), 'ada')
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('Date of Birth'), '1990-01-01')
  await userEvent.type(screen.getByLabelText('Password'), 'pass')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'pass')
  await userEvent.click(screen.getByRole('button', { name: 'Register' }))
  await userEvent.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('shows error banner on failed registration', async () => {
  mockRegister.mockRejectedValueOnce({ message: 'Username already taken' })
  renderRegisterPage()
  await userEvent.type(screen.getByLabelText('Username'), 'ada')
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('Date of Birth'), '1990-01-01')
  await userEvent.type(screen.getByLabelText('Password'), 'pass')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'pass')
  await userEvent.click(screen.getByRole('button', { name: 'Register' }))
  await userEvent.click(screen.getByRole('button', { name: 'Ok' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Username already taken')
})

test('navigates to home on successful registration', async () => {
  mockRegister.mockResolvedValueOnce({
    session_management_token: 'tok',
    user_id: 'uuid-abc',
    username: 'ada',
  })
  renderRegisterPage()
  await userEvent.type(screen.getByLabelText('Username'), 'ada')
  await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
  await userEvent.type(screen.getByLabelText('Date of Birth'), '1990-01-01')
  await userEvent.type(screen.getByLabelText('Password'), 'pass')
  await userEvent.type(screen.getByLabelText('Confirm Password'), 'pass')
  await userEvent.click(screen.getByRole('button', { name: 'Register' }))
  await userEvent.click(screen.getByRole('button', { name: 'Ok' }))
  expect(await screen.findByText('Home')).toBeInTheDocument()
})
