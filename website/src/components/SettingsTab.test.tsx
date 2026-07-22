import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import SettingsTab from './SettingsTab'

vi.mock('../api/client', () => ({
  apiClient: {
    logout: vi.fn(),
    deleteAccount: vi.fn(),
    verifyIdentity: vi.fn(),
    setToken: vi.fn(),
    setupTotp: vi.fn(),
    confirmTotp: vi.fn(),
    disableTotp: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockLogout = vi.mocked(apiClient.logout)
const mockDelete = vi.mocked(apiClient.deleteAccount)
const mockVerify = vi.mocked(apiClient.verifyIdentity)
const mockSetupTotp = vi.mocked(apiClient.setupTotp)
const mockConfirmTotp = vi.mocked(apiClient.confirmTotp)
const mockDisableTotp = vi.mocked(apiClient.disableTotp)

function renderTab() {
  return render(
    <MemoryRouter initialEntries={['/home']}>
      <Routes>
        <Route path="/home" element={<SettingsTab />} />
        <Route path="/" element={<div>Landing page</div>} />
        <Route path="/appeals" element={<div>Appeals page</div>} />
        <Route path="/blocked" element={<div>Blocked users page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockLogout.mockReset().mockResolvedValue({ message: 'ok' })
  mockDelete.mockReset().mockResolvedValue({ message: 'ok' })
  mockVerify.mockReset().mockResolvedValue({ message: 'ok' })
  mockSetupTotp.mockReset().mockResolvedValue({
    totp_secret: 'STUBSECRETBASE32',
    otpauth_uri: 'otpauth://totp/Positive%20Only%20Social:ada?secret=STUBSECRETBASE32',
  })
  mockConfirmTotp.mockReset().mockResolvedValue({
    totp_enabled: true,
    recovery_codes: ['aaaaaaaaaa', 'bbbbbbbbbb'],
  })
  mockDisableTotp.mockReset().mockResolvedValue({ totp_enabled: false })
  vi.stubGlobal('localStorage', {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('logout requires confirmation then signs out', async () => {
  renderTab()
  await userEvent.click(screen.getByRole('button', { name: 'Logout' }))
  // Confirm dialog appears.
  await userEvent.click(
    screen.getByRole('dialog', { name: /log out/i }).querySelector('.modal__confirm')!,
  )
  expect(mockLogout).toHaveBeenCalled()
  expect(await screen.findByText('Landing page')).toBeInTheDocument()
})

test('delete account requires confirmation then deletes', async () => {
  renderTab()
  await userEvent.click(screen.getByRole('button', { name: 'Delete Account' }))
  await userEvent.click(
    screen.getByRole('dialog', { name: /delete your account/i }).querySelector('.modal__confirm')!,
  )
  expect(mockDelete).toHaveBeenCalled()
  expect(await screen.findByText('Landing page')).toBeInTheDocument()
})

test('verify identity submits the date of birth', async () => {
  renderTab()
  await userEvent.click(screen.getByRole('button', { name: 'Verify Identity' }))
  await userEvent.type(screen.getByLabelText('Date of birth'), '1990-01-01')
  await userEvent.click(screen.getByRole('button', { name: 'Verify' }))
  expect(mockVerify).toHaveBeenCalledWith('1990-01-01')
  expect(await screen.findByText('Identity verified successfully!')).toBeInTheDocument()
})

test('privacy policy can be shown', async () => {
  renderTab()
  await userEvent.click(screen.getByRole('button', { name: 'Privacy Policy' }))
  expect(screen.getByRole('dialog', { name: 'Privacy Policy' })).toBeInTheDocument()
})

test('opens the hidden content & appeals page', async () => {
  renderTab()
  await userEvent.click(screen.getByRole('button', { name: 'Hidden Content & Appeals' }))
  expect(await screen.findByText('Appeals page')).toBeInTheDocument()
})

test('enabling 2fa walks through scan, confirm, and recovery codes', async () => {
  renderTab()
  await userEvent.click(screen.getByRole('button', { name: 'Enable Two-Factor Authentication' }))

  // Scan step: the secret from setup is shown.
  expect(await screen.findByText('STUBSECRETBASE32')).toBeInTheDocument()
  expect(mockSetupTotp).toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: 'Next' }))

  // Confirm step: six-digit code gates the Verify button.
  const codeInput = screen.getByLabelText('Authenticator code')
  expect(screen.getByRole('button', { name: 'Verify' })).toBeDisabled()
  await userEvent.type(codeInput, '123456')
  await userEvent.click(screen.getByRole('button', { name: 'Verify' }))

  expect(mockConfirmTotp).toHaveBeenCalledWith({ totp_code: '123456' })

  // Recovery codes are displayed once.
  expect(await screen.findByText('aaaaaaaaaa')).toBeInTheDocument()
  expect(screen.getByText('bbbbbbbbbb')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Done' }))

  expect(screen.getByText('Two-factor authentication is now enabled.')).toBeInTheDocument()
})

test('a wrong confirmation code surfaces the error and stays open', async () => {
  // The module mock above doesn't re-export ApiError; a plain object with a
  // message is what the component reads either way.
  mockConfirmTotp.mockRejectedValueOnce({ message: 'Invalid two-factor code' })
  renderTab()
  await userEvent.click(screen.getByRole('button', { name: 'Enable Two-Factor Authentication' }))
  await screen.findByText('STUBSECRETBASE32')
  await userEvent.click(screen.getByRole('button', { name: 'Next' }))
  await userEvent.type(screen.getByLabelText('Authenticator code'), '000000')
  await userEvent.click(screen.getByRole('button', { name: 'Verify' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid two-factor code')
  // Still on the confirm step, so the user can retry.
  expect(screen.getByLabelText('Authenticator code')).toBeInTheDocument()
})

test('disabling 2fa sends the password and code', async () => {
  renderTab()
  await userEvent.click(screen.getByRole('button', { name: 'Disable Two-Factor Authentication' }))

  await userEvent.type(screen.getByLabelText('Password'), 'MyPassword1-')
  await userEvent.type(screen.getByLabelText('Authenticator code'), '654321')
  await userEvent.click(screen.getByRole('button', { name: 'Disable' }))

  expect(mockDisableTotp).toHaveBeenCalledWith({ password: 'MyPassword1-', totp_code: '654321' })
  expect(
    await screen.findByText('Two-factor authentication has been disabled.'),
  ).toBeInTheDocument()
})

test('disabling 2fa can use a recovery code instead', async () => {
  renderTab()
  await userEvent.click(screen.getByRole('button', { name: 'Disable Two-Factor Authentication' }))

  await userEvent.click(screen.getByRole('button', { name: 'Use a recovery code instead' }))
  await userEvent.type(screen.getByLabelText('Password'), 'MyPassword1-')
  await userEvent.type(screen.getByLabelText('Recovery code'), 'ABCDEF0123')
  await userEvent.click(screen.getByRole('button', { name: 'Disable' }))

  // Recovery codes are sent lowercased to match the backend pattern.
  expect(mockDisableTotp).toHaveBeenCalledWith({
    password: 'MyPassword1-',
    recovery_code: 'abcdef0123',
  })
})

test('opens the blocked users page', async () => {
  renderTab()
  await userEvent.click(screen.getByRole('button', { name: 'Blocked Users' }))
  expect(await screen.findByText('Blocked users page')).toBeInTheDocument()
})
