import { act, cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import PrivacyPolicyReacceptGate from './PrivacyPolicyReacceptGate'
import {
  hasAcceptedPrivacyPolicy,
  markPrivacyPolicyAccepted,
  resetPrivacyPolicyAcceptance,
} from '../auth/privacyPolicyConsent'
import { clearSession, persistSession } from '../api/session'
import { PRIVACY_POLICY_TEXT } from '../privacyPolicy'

vi.mock('../api/client', () => ({
  apiClient: {
    logout: vi.fn(),
    setToken: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockLogout = vi.mocked(apiClient.logout)

/** A real-behaving in-memory Storage: this environment doesn't provide one. */
function createMemoryStorage(): Storage {
  const values = new Map<string, string>()
  return {
    get length() {
      return values.size
    },
    clear: () => values.clear(),
    getItem: key => values.get(key) ?? null,
    key: index => Array.from(values.keys())[index] ?? null,
    removeItem: key => {
      values.delete(key)
    },
    setItem: (key, value) => {
      values.set(key, String(value))
    },
  }
}

function signIn() {
  sessionStorage.setItem('session_token', 'token-123')
  sessionStorage.setItem('user_id', 'user-1')
  sessionStorage.setItem('username', 'adalovelace')
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<div>Landing</div>} />
        <Route path="/home" element={<div>Home</div>} />
        <Route path="/login" element={<div>Login</div>} />
        <Route path="/delete-account" element={<div>Delete Account</div>} />
        <Route path="/privacy-policy" element={<div>Policy Page</div>} />
        <Route path="/profile/:username" element={<div>Profile</div>} />
      </Routes>
      <PrivacyPolicyReacceptGate />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.stubGlobal('localStorage', createMemoryStorage())
  vi.stubGlobal('sessionStorage', createMemoryStorage())
  resetPrivacyPolicyAcceptance()
  mockLogout.mockReset().mockResolvedValue({ message: 'ok' })
})

afterEach(() => {
  // Unmount before resetting: the reset re-renders a mounted gate, which would
  // then read storage after it has been unstubbed.
  cleanup()
  resetPrivacyPolicyAcceptance()
  vi.unstubAllGlobals()
})

test('asks a signed-in user to accept the privacy policy on an app page', () => {
  signIn()
  renderAt('/home')

  expect(screen.getByRole('dialog', { name: 'Privacy Policy Updated' })).toBeInTheDocument()
  expect(screen.getByText(PRIVACY_POLICY_TEXT)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Accept' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Log Out' })).toBeInTheDocument()
})

test('gates nested authenticated routes too, not just /home', () => {
  signIn()
  renderAt('/profile/someone')

  expect(screen.getByRole('dialog', { name: 'Privacy Policy Updated' })).toBeInTheDocument()
})

test('accepting closes the dialog and keeps the user signed in', async () => {
  signIn()
  renderAt('/home')

  await userEvent.click(screen.getByRole('button', { name: 'Accept' }))

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByText('Home')).toBeInTheDocument()
  expect(hasAcceptedPrivacyPolicy()).toBe(true)
  expect(sessionStorage.getItem('session_token')).toBe('token-123')
  expect(mockLogout).not.toHaveBeenCalled()
})

test('declining logs the user out and returns to the landing page', async () => {
  signIn()
  renderAt('/home')

  await userEvent.click(screen.getByRole('button', { name: 'Log Out' }))

  expect(mockLogout).toHaveBeenCalledTimes(1)
  expect(sessionStorage.getItem('session_token')).toBeNull()
  expect(await screen.findByText('Landing')).toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('declining still logs out locally when the backend logout fails', async () => {
  mockLogout.mockRejectedValue(new Error('network'))
  signIn()
  renderAt('/home')

  await userEvent.click(screen.getByRole('button', { name: 'Log Out' }))

  expect(sessionStorage.getItem('session_token')).toBeNull()
  expect(await screen.findByText('Landing')).toBeInTheDocument()
})

test('does not show when nobody is signed in', () => {
  renderAt('/home')

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test.each(['/', '/login', '/delete-account', '/privacy-policy'])(
  'does not show on the signed-out page %s even with a stored session',
  path => {
    signIn()
    renderAt(path)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  },
)

test('does not show again once accepted this session', () => {
  signIn()
  markPrivacyPolicyAccepted()
  renderAt('/home')

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('logging out forgets the acceptance, so the next sign-in is asked again', () => {
  signIn()
  markPrivacyPolicyAccepted()
  const { unmount } = renderAt('/home')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  unmount()

  act(() => {
    clearSession()
  })
  expect(hasAcceptedPrivacyPolicy()).toBe(false)

  signIn()
  renderAt('/home')
  expect(screen.getByRole('dialog', { name: 'Privacy Policy Updated' })).toBeInTheDocument()
})

test('a new sign-in is asked again even without a logout in between', () => {
  signIn()
  markPrivacyPolicyAccepted()

  act(() => {
    persistSession({ session_management_token: 'token-456', user_id: 'user-2' }, false)
  })

  expect(hasAcceptedPrivacyPolicy()).toBe(false)
  renderAt('/home')
  expect(screen.getByRole('dialog', { name: 'Privacy Policy Updated' })).toBeInTheDocument()
})
