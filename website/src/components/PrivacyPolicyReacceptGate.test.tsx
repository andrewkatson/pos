import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
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
import { POLICY_VERSION, PRIVACY_POLICY_TEXT } from '../privacyPolicy'

vi.mock('../api/client', () => ({
  apiClient: {
    logout: vi.fn(),
    setToken: vi.fn(),
    getCurrentUser: vi.fn(),
    acceptPolicies: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockLogout = vi.mocked(apiClient.logout)
const mockGetCurrentUser = vi.mocked(apiClient.getCurrentUser)
const mockAcceptPolicies = vi.mocked(apiClient.acceptPolicies)

/** What GET /me/ reports as the member's last accepted policy version. */
function onRecord(version: string | null) {
  mockGetCurrentUser.mockResolvedValue({
    username: 'adalovelace',
    email: 'ada@example.com',
    policies_accepted_version: version,
  })
}

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
      <PrivacyPolicyReacceptGate>
        <Routes>
          <Route path="/" element={<div>Landing</div>} />
          <Route
              path="/home"
              element={
                <div>
                  Home <button type="button">Open settings</button>
                </div>
              }
            />
          <Route path="/login" element={<div>Login</div>} />
          <Route path="/delete-account" element={<div>Delete Account</div>} />
          <Route path="/privacy-policy" element={<div>Policy Page</div>} />
          <Route path="/profile/:username" element={<div>Profile</div>} />
        </Routes>
      </PrivacyPolicyReacceptGate>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.stubGlobal('localStorage', createMemoryStorage())
  vi.stubGlobal('sessionStorage', createMemoryStorage())
  resetPrivacyPolicyAcceptance()
  mockLogout.mockReset().mockResolvedValue({ message: 'ok' })
  mockGetCurrentUser.mockReset()
  onRecord(null)
  mockAcceptPolicies.mockReset().mockResolvedValue({ policies_accepted_version: POLICY_VERSION })
})

afterEach(() => {
  // Unmount before resetting: the reset re-renders a mounted gate, which would
  // then read storage after it has been unstubbed.
  cleanup()
  resetPrivacyPolicyAcceptance()
  vi.unstubAllGlobals()
})

test('asks a signed-in user to accept the privacy policy on an app page', async () => {
  signIn()
  renderAt('/home')

  expect(await screen.findByRole('dialog', { name: 'Privacy Policy Updated' })).toBeInTheDocument()
  expect(screen.getByText(PRIVACY_POLICY_TEXT)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Accept' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Log Out' })).toBeInTheDocument()
})

test('gates nested authenticated routes too, not just /home', async () => {
  signIn()
  renderAt('/profile/someone')

  expect(await screen.findByRole('dialog', { name: 'Privacy Policy Updated' })).toBeInTheDocument()
})

test('keeps the page behind the dialog inert until the user answers', async () => {
  signIn()
  renderAt('/home')

  // Inert content is unreachable by mouse and by Tab, so the dialog's own
  // buttons are the only controls left.
  await screen.findByRole('dialog')
  const pageButton = screen.getByText('Open settings', { selector: 'button' })
  expect(pageButton.closest('[inert]')).not.toBeNull()
  expect(screen.getByRole('button', { name: 'Accept' }).closest('[inert]')).toBeNull()

  await userEvent.click(screen.getByRole('button', { name: 'Accept' }))

  expect(pageButton.closest('[inert]')).toBeNull()
})

test('the policy text scrolls inside the dialog, apart from the buttons', async () => {
  signIn()
  renderAt('/home')

  const policy = await screen.findByRole('region', { name: 'Privacy Policy' })
  expect(policy).toHaveClass('privacy-reaccept__policy')
  expect(policy).toHaveTextContent(PRIVACY_POLICY_TEXT)
  expect(policy).not.toContainElement(screen.getByRole('button', { name: 'Accept' }))
})

test('the page is not inert when there is nothing to answer', () => {
  renderAt('/home')

  expect(screen.getByText('Open settings', { selector: 'button' }).closest('[inert]')).toBeNull()
})

test('accepting closes the dialog and keeps the user signed in', async () => {
  signIn()
  renderAt('/home')

  await userEvent.click(await screen.findByRole('button', { name: 'Accept' }))

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByText('Home')).toBeInTheDocument()
  expect(hasAcceptedPrivacyPolicy()).toBe(true)
  expect(sessionStorage.getItem('session_token')).toBe('token-123')
  expect(mockLogout).not.toHaveBeenCalled()
})

test('accepting records the bundled policy version on the backend', async () => {
  signIn()
  renderAt('/home')

  await userEvent.click(await screen.findByRole('button', { name: 'Accept' }))

  expect(mockAcceptPolicies).toHaveBeenCalledTimes(1)
  expect(mockAcceptPolicies).toHaveBeenCalledWith({ policy_version: POLICY_VERSION })
})

test('accepting still lets the user in when recording it fails', async () => {
  mockAcceptPolicies.mockRejectedValue(new Error('network'))
  signIn()
  renderAt('/home')

  await userEvent.click(await screen.findByRole('button', { name: 'Accept' }))

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(hasAcceptedPrivacyPolicy()).toBe(true)
})

test('does not ask when the backend records this version as accepted', async () => {
  onRecord(POLICY_VERSION)
  signIn()
  renderAt('/home')

  await waitFor(() => expect(hasAcceptedPrivacyPolicy()).toBe(true))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByText('Open settings', { selector: 'button' }).closest('[inert]')).toBeNull()
  expect(mockGetCurrentUser).toHaveBeenCalledTimes(1)
  expect(mockAcceptPolicies).not.toHaveBeenCalled()
})

test('does not ask when the backend records a newer version as accepted', async () => {
  onRecord('9999-12-31')
  signIn()
  renderAt('/home')

  await waitFor(() => expect(hasAcceptedPrivacyPolicy()).toBe(true))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('asks when the version on record is older than this build’s', async () => {
  onRecord('2000-01-01')
  signIn()
  renderAt('/home')

  expect(await screen.findByRole('dialog', { name: 'Privacy Policy Updated' })).toBeInTheDocument()
})

test('asks when the backend check fails', async () => {
  mockGetCurrentUser.mockRejectedValue(new Error('network'))
  signIn()
  renderAt('/home')

  expect(await screen.findByRole('dialog', { name: 'Privacy Policy Updated' })).toBeInTheDocument()
})

test('keeps the page inert, with no dialog yet, while the check is in flight', async () => {
  let resolve: (value: Awaited<ReturnType<typeof apiClient.getCurrentUser>>) => void = () => {}
  mockGetCurrentUser.mockReturnValue(new Promise(r => (resolve = r)))
  signIn()
  renderAt('/home')

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByText('Open settings', { selector: 'button' }).closest('[inert]')).not.toBeNull()

  await act(async () => {
    resolve({ username: 'adalovelace', email: 'ada@example.com', policies_accepted_version: POLICY_VERSION })
  })
  expect(screen.getByText('Open settings', { selector: 'button' }).closest('[inert]')).toBeNull()
})

test('a check still in flight when the session changes does not settle the next one', async () => {
  let resolve: (value: Awaited<ReturnType<typeof apiClient.getCurrentUser>>) => void = () => {}
  mockGetCurrentUser.mockReturnValueOnce(new Promise(r => (resolve = r)))
  signIn()
  const { unmount } = renderAt('/home')
  unmount()

  act(() => {
    persistSession({ session_management_token: 'token-456', user_id: 'user-2' }, false)
  })
  await act(async () => {
    resolve({ username: 'adalovelace', email: 'ada@example.com', policies_accepted_version: POLICY_VERSION })
  })

  expect(hasAcceptedPrivacyPolicy()).toBe(false)
})

test('declining logs the user out and returns to the landing page', async () => {
  signIn()
  renderAt('/home')

  await userEvent.click(await screen.findByRole('button', { name: 'Log Out' }))

  expect(mockLogout).toHaveBeenCalledTimes(1)
  expect(sessionStorage.getItem('session_token')).toBeNull()
  expect(await screen.findByText('Landing')).toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('declining still logs out locally when the backend logout fails', async () => {
  mockLogout.mockRejectedValue(new Error('network'))
  signIn()
  renderAt('/home')

  await userEvent.click(await screen.findByRole('button', { name: 'Log Out' }))

  expect(sessionStorage.getItem('session_token')).toBeNull()
  expect(await screen.findByText('Landing')).toBeInTheDocument()
})

test('does not show, or ask the backend, when nobody is signed in', () => {
  renderAt('/home')

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(mockGetCurrentUser).not.toHaveBeenCalled()
})

test.each(['/', '/login', '/delete-account', '/privacy-policy'])(
  'does not show on the signed-out page %s even with a stored session',
  path => {
    signIn()
    renderAt(path)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(mockGetCurrentUser).not.toHaveBeenCalled()
  },
)

test('does not show again, or re-check, once accepted this session', () => {
  signIn()
  markPrivacyPolicyAccepted()
  renderAt('/home')

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(mockGetCurrentUser).not.toHaveBeenCalled()
})

test('logging out forgets the acceptance, so the next sign-in is checked again', async () => {
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
  expect(await screen.findByRole('dialog', { name: 'Privacy Policy Updated' })).toBeInTheDocument()
})

test('a new sign-in is checked again even without a logout in between', async () => {
  signIn()
  markPrivacyPolicyAccepted()

  act(() => {
    persistSession({ session_management_token: 'token-456', user_id: 'user-2' }, false)
  })

  expect(hasAcceptedPrivacyPolicy()).toBe(false)
  renderAt('/home')
  expect(await screen.findByRole('dialog', { name: 'Privacy Policy Updated' })).toBeInTheDocument()
})
