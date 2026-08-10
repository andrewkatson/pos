import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import {
  GOOGLE_IDENTITY_SCRIPT_URL,
  googleClientId,
  isGoogleSignInConfigured,
  loadGoogleIdentityServices,
  resetGoogleIdentityServicesForTests,
} from './googleIdentity'

/** Stand-in for the `google` global the real GIS script installs. */
function fakeGoogle() {
  return {
    id: {
      initialize: vi.fn(),
      renderButton: vi.fn(),
      disableAutoSelect: vi.fn(),
    },
  }
}

function scriptTag(): HTMLScriptElement | null {
  return document.querySelector(`script[src="${GOOGLE_IDENTITY_SCRIPT_URL}"]`)
}

beforeEach(() => {
  resetGoogleIdentityServicesForTests()
  document.head.innerHTML = ''
  delete window.google
})

afterEach(() => {
  vi.unstubAllEnvs()
})

test('an unset client ID turns Google sign-in off', () => {
  vi.stubEnv('VITE_GOOGLE_CLIENT_ID', '')
  expect(isGoogleSignInConfigured()).toBe(false)
})

test('a whitespace-only client ID counts as unset', () => {
  vi.stubEnv('VITE_GOOGLE_CLIENT_ID', '   ')
  expect(isGoogleSignInConfigured()).toBe(false)
  expect(googleClientId()).toBe('')
})

test('a configured client ID turns Google sign-in on', () => {
  vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'web.apps.googleusercontent.com')
  expect(isGoogleSignInConfigured()).toBe(true)
  expect(googleClientId()).toBe('web.apps.googleusercontent.com')
})

test('the script is appended once and resolves with the google global', async () => {
  const pending = loadGoogleIdentityServices()

  const script = scriptTag()
  expect(script).not.toBeNull()
  expect(script?.async).toBe(true)

  window.google = fakeGoogle()
  script?.dispatchEvent(new Event('load'))

  await expect(pending).resolves.toBe(window.google)
})

test('concurrent callers share one script tag', async () => {
  const first = loadGoogleIdentityServices()
  const second = loadGoogleIdentityServices()

  expect(document.querySelectorAll(`script[src="${GOOGLE_IDENTITY_SCRIPT_URL}"]`)).toHaveLength(1)

  window.google = fakeGoogle()
  scriptTag()?.dispatchEvent(new Event('load'))

  expect(await first).toBe(await second)
})

test('an already-loaded google global short-circuits the script', async () => {
  window.google = fakeGoogle()

  await expect(loadGoogleIdentityServices()).resolves.toBe(window.google)
  expect(scriptTag()).toBeNull()
})

test('a failed load rejects and can be retried', async () => {
  const first = loadGoogleIdentityServices()
  const firstScript = scriptTag()
  firstScript?.dispatchEvent(new Event('error'))
  await expect(first).rejects.toThrow('Could not load Google Identity Services')

  // The dead tag is removed, not left for the retry to adopt: a script that has
  // already fired error never fires load or error again, so reusing it would
  // leave the retry's promise unsettled forever.
  expect(scriptTag()).toBeNull()

  // And the cached promise is dropped, so a blocked or offline first attempt
  // does not disable the button for the rest of the session.
  const second = loadGoogleIdentityServices()
  const secondScript = scriptTag()
  expect(secondScript).not.toBeNull()
  expect(secondScript).not.toBe(firstScript)

  window.google = fakeGoogle()
  secondScript?.dispatchEvent(new Event('load'))
  await expect(second).resolves.toBe(window.google)
})

test('a script that loads without installing an id API is a failure', async () => {
  const pending = loadGoogleIdentityServices()
  scriptTag()?.dispatchEvent(new Event('load'))
  await expect(pending).rejects.toThrow('without an id API')
})

test('a script that loads without an id API is retried like any other failure', async () => {
  // The load-fired-but-nothing-installed path is just as transient as a network
  // failure, so it must clean up identically — otherwise the first bad load
  // permanently disables the button.
  const first = loadGoogleIdentityServices()
  const firstScript = scriptTag()
  firstScript?.dispatchEvent(new Event('load'))
  await expect(first).rejects.toThrow('without an id API')

  expect(scriptTag()).toBeNull()

  const second = loadGoogleIdentityServices()
  const secondScript = scriptTag()
  expect(secondScript).not.toBe(firstScript)

  window.google = fakeGoogle()
  secondScript?.dispatchEvent(new Event('load'))
  await expect(second).resolves.toBe(window.google)
})

test('a stale tag left in the DOM is not adopted', async () => {
  // Anything already in the document may have fired its events long ago, so a
  // fresh attempt always gets its own element rather than attaching listeners
  // to one that can never fire again.
  const stale = document.createElement('script')
  stale.src = GOOGLE_IDENTITY_SCRIPT_URL
  document.head.appendChild(stale)

  const pending = loadGoogleIdentityServices()
  const tags = document.querySelectorAll(`script[src="${GOOGLE_IDENTITY_SCRIPT_URL}"]`)
  const ours = Array.from(tags).find(tag => tag !== stale)
  expect(ours).toBeDefined()

  window.google = fakeGoogle()
  ours?.dispatchEvent(new Event('load'))
  await expect(pending).resolves.toBe(window.google)
})
