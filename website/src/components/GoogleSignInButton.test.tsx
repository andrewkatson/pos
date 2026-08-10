import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import GoogleSignInButton from './GoogleSignInButton'
import type { GoogleCredentialResponse, GoogleIdentityServices } from '../auth/googleIdentity'

const loadGoogleIdentityServices = vi.hoisted(() => vi.fn())

vi.mock('../auth/googleIdentity', async importOriginal => {
  const actual = await importOriginal<typeof import('../auth/googleIdentity')>()
  return { ...actual, loadGoogleIdentityServices }
})

/** Captures the callback GIS would invoke, so a test can "pick an account". */
function fakeGoogle() {
  let callback: ((response: GoogleCredentialResponse) => void) | null = null
  const google = {
    id: {
      initialize: vi.fn((config: { callback: (r: GoogleCredentialResponse) => void }) => {
        callback = config.callback
      }),
      renderButton: vi.fn(),
      disableAutoSelect: vi.fn(),
    },
  }
  return {
    google: google as unknown as GoogleIdentityServices,
    signInAs: (credential: string) => callback?.({ credential }),
    google_: google,
  }
}

beforeEach(() => {
  vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'web.apps.googleusercontent.com')
  loadGoogleIdentityServices.mockReset()
})

afterEach(() => {
  vi.unstubAllEnvs()
})

test('renders nothing when no client ID is configured', () => {
  vi.stubEnv('VITE_GOOGLE_CLIENT_ID', '')
  render(<GoogleSignInButton onCredential={vi.fn()} />)

  expect(screen.queryByTestId('google-sign-in-button')).not.toBeInTheDocument()
  expect(loadGoogleIdentityServices).not.toHaveBeenCalled()
})

test('hands the container to Google and reports the credential it returns', async () => {
  const { google, signInAs, google_ } = fakeGoogle()
  loadGoogleIdentityServices.mockResolvedValue(google)
  const onCredential = vi.fn()

  render(<GoogleSignInButton onCredential={onCredential} />)

  await waitFor(() => expect(google_.id.renderButton).toHaveBeenCalled())
  expect(google_.id.renderButton.mock.calls[0][0]).toBe(screen.getByTestId('google-sign-in-button'))

  signInAs('an.id.token')
  expect(onCredential).toHaveBeenCalledWith('an.id.token')
})

test('never signs someone in without them asking', async () => {
  const { google, google_ } = fakeGoogle()
  loadGoogleIdentityServices.mockResolvedValue(google)

  render(<GoogleSignInButton onCredential={vi.fn()} />)

  await waitFor(() => expect(google_.id.initialize).toHaveBeenCalled())
  expect(google_.id.initialize.mock.calls[0][0]).toMatchObject({
    client_id: 'web.apps.googleusercontent.com',
    auto_select: false,
  })
})

test('the button label follows the page it is on', async () => {
  const { google, google_ } = fakeGoogle()
  loadGoogleIdentityServices.mockResolvedValue(google)

  render(<GoogleSignInButton onCredential={vi.fn()} text="signup_with" />)

  await waitFor(() => expect(google_.id.renderButton).toHaveBeenCalled())
  expect(google_.id.renderButton.mock.calls[0][1]).toMatchObject({ text: 'signup_with' })
})

test('hides the button while a sign-in is already in flight', async () => {
  const { google, google_ } = fakeGoogle()
  loadGoogleIdentityServices.mockResolvedValue(google)

  render(<GoogleSignInButton onCredential={vi.fn()} disabled />)

  await waitFor(() => expect(google_.id.renderButton).toHaveBeenCalled())
  // Google's button is an iframe that can't carry a `disabled` attribute, so a
  // second click is prevented by hiding it outright.
  expect(screen.getByTestId('google-sign-in-button')).toHaveAttribute('hidden')
  // ...and the divider goes with it, rather than being left over the gap where
  // the button used to be.
  expect(screen.queryByText('or')).not.toBeInTheDocument()
})

test('the divider appears once there is a button under it', async () => {
  const { google, google_ } = fakeGoogle()
  loadGoogleIdentityServices.mockResolvedValue(google)

  render(<GoogleSignInButton onCredential={vi.fn()} />)

  await waitFor(() => expect(google_.id.renderButton).toHaveBeenCalled())
  expect(screen.getByText('or')).toBeInTheDocument()
})

test('reports a failure to reach Google instead of showing a dead button', async () => {
  loadGoogleIdentityServices.mockRejectedValue(new Error('offline'))
  const onError = vi.fn()

  render(<GoogleSignInButton onCredential={vi.fn()} onError={onError} />)

  await waitFor(() => expect(onError).toHaveBeenCalled())
  expect(onError.mock.calls[0][0]).toContain('Google sign-in is unavailable')
})

test('the caller chooses the unavailable copy, since the way out differs per page', async () => {
  // The login page can say "use your password"; someone signing up with Google
  // has no account yet, so that wording would be nonsense there.
  loadGoogleIdentityServices.mockRejectedValue(new Error('offline'))
  const onError = vi.fn()

  render(
    <GoogleSignInButton
      onCredential={vi.fn()}
      onError={onError}
      text="signup_with"
      unavailableMessage="Google sign-up is unavailable right now. Please fill in the form above instead."
    />,
  )

  await waitFor(() => expect(onError).toHaveBeenCalled())
  expect(onError.mock.calls[0][0]).toBe(
    'Google sign-up is unavailable right now. Please fill in the form above instead.',
  )
  expect(onError.mock.calls[0][0]).not.toContain('your password')
})
