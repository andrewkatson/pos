import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { profilePathFor } from './profilePath'

function stubStoredUsername(username: string | null) {
  vi.stubGlobal('localStorage', {
    getItem: vi.fn((key: string) => (key === 'username' ? username : null)),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  })
  vi.stubGlobal('sessionStorage', {
    getItem: vi.fn(() => null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  })
}

beforeEach(() => {
  stubStoredUsername('ada')
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('your own name routes to the Profile tab, not the pushed profile route', () => {
  // The app shell opens on the Profile tab, so /home lands on your own profile
  // with the bottom bar intact rather than a back-stacked copy (issue #347).
  expect(profilePathFor('ada')).toBe('/home')
})

test('another user routes to their profile page', () => {
  expect(profilePathFor('bob')).toBe('/profile/bob')
})

test('usernames are URL-encoded', () => {
  expect(profilePathFor('a b')).toBe('/profile/a%20b')
})

test('a signed-out viewer routes everyone to the profile page', () => {
  stubStoredUsername(null)
  expect(profilePathFor('ada')).toBe('/profile/ada')
})
