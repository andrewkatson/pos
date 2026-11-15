import { test, expect } from 'vitest'
import { isPublicPath, PUBLIC_PATHS } from './publicPaths'

test('every listed path is public', () => {
  for (const path of PUBLIC_PATHS) {
    expect(isPublicPath(path)).toBe(true)
  }
})

test('the App Store support URL is public', () => {
  expect(isPublicPath('/support')).toBe(true)
})

test('a trailing slash still matches', () => {
  expect(isPublicPath('/support/')).toBe(true)
})

test('repeated trailing slashes still match, as they do in the router', () => {
  expect(isPublicPath('/support//')).toBe(true)
  expect(isPublicPath('/privacy-policy///')).toBe(true)
})

test('casing is ignored, as it is in the router', () => {
  expect(isPublicPath('/Support')).toBe(true)
  expect(isPublicPath('/TERMS-OF-SERVICE/')).toBe(true)
})

test('the root path is not public', () => {
  expect(isPublicPath('/')).toBe(false)
  expect(isPublicPath('')).toBe(false)
})

test('signed-in and sign-in pages are not public', () => {
  expect(isPublicPath('/home')).toBe(false)
  expect(isPublicPath('/login')).toBe(false)
  // The deletion page signs the visitor in itself, so it keeps the redirects.
  expect(isPublicPath('/delete-account')).toBe(false)
})

test('a path that merely starts with a public one is not public', () => {
  expect(isPublicPath('/supportive')).toBe(false)
  expect(isPublicPath('/support/ticket')).toBe(false)
})
