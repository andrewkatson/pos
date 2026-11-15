import { vi, beforeEach, test, expect } from 'vitest'

// Capture the handlers the installer hands to the client, so each test can
// fire them the way a failing startup request would.
const handlers: {
  onAccountBanned?: () => void
  onEmailNotVerified?: () => void
} = {}

vi.mock('./client', () => ({
  apiClient: {
    setOnAccountBanned: (fn: () => void) => {
      handlers.onAccountBanned = fn
    },
    setOnEmailNotVerified: (fn: () => void) => {
      handlers.onEmailNotVerified = fn
    },
  },
}))

vi.mock('./session', () => ({
  clearSession: vi.fn(),
}))

import { installAuthFailureHandlers } from './authFailureRedirects'
import { clearSession } from './session'

const mockClearSession = vi.mocked(clearSession)

function install(pathname: string) {
  const assign = vi.fn()
  installAuthFailureHandlers({ pathname: () => pathname, assign })
  return assign
}

beforeEach(() => {
  mockClearSession.mockReset()
  handlers.onAccountBanned = undefined
  handlers.onEmailNotVerified = undefined
})

test('a suspended session on a private page lands on the login page', () => {
  const assign = install('/home')

  handlers.onAccountBanned!()

  expect(mockClearSession).toHaveBeenCalled()
  expect(assign).toHaveBeenCalledWith('/login?suspended=1')
})

test('an unverified session on a private page lands on the login page', () => {
  const assign = install('/home')

  handlers.onEmailNotVerified!()

  expect(mockClearSession).toHaveBeenCalled()
  expect(assign).toHaveBeenCalledWith('/login?verify_email=1')
})

// The support page exists for people who cannot sign in. Startup work on a
// stored suspended/unverified session used to bounce them to /login, taking
// Apple's Support URL down for exactly its audience.
test('a suspended session stays on the support page', () => {
  const assign = install('/support')

  handlers.onAccountBanned!()

  expect(mockClearSession).toHaveBeenCalled()
  expect(assign).not.toHaveBeenCalled()
})

test('an unverified session stays on the support page', () => {
  const assign = install('/support')

  handlers.onEmailNotVerified!()

  expect(mockClearSession).toHaveBeenCalled()
  expect(assign).not.toHaveBeenCalled()
})

test.each(['/privacy-policy', '/terms-of-service', '/support/'])(
  'a suspended session stays on %s',
  path => {
    const assign = install(path)

    handlers.onAccountBanned!()

    expect(assign).not.toHaveBeenCalled()
  },
)

// /delete-account signs the visitor in itself and reports these errors in the
// form, so it is not a public path and keeps the redirect.
test('the deletion page still redirects a suspended session', () => {
  const assign = install('/delete-account')

  handlers.onAccountBanned!()

  expect(assign).toHaveBeenCalledWith('/login?suspended=1')
})
