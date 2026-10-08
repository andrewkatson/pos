import { describe, expect, test } from 'vitest'
import {
  allMet,
  getUsernameRequirements,
  MAX_USERNAME_LENGTH,
  MIN_USERNAME_LENGTH,
} from './requirements'

// The username rule must match the backend's Patterns.username: 10-150, where
// 150 is the username column's max_length. A looser bound lets a 151-500
// character name through to a database failure at registration.
function lengthMet(username: string): boolean {
  return getUsernameRequirements(username)[0].didMeetRequirement
}

describe('getUsernameRequirements', () => {
  test('bounds match the backend', () => {
    expect(MIN_USERNAME_LENGTH).toBe(10)
    expect(MAX_USERNAME_LENGTH).toBe(150)
    expect(getUsernameRequirements('')[0].label).toBe('Between 10 and 150 characters')
  })

  test('accepts 10 through 150 characters', () => {
    expect(lengthMet('a'.repeat(9))).toBe(false)
    expect(lengthMet('a'.repeat(10))).toBe(true)
    expect(lengthMet('a'.repeat(150))).toBe(true)
    expect(lengthMet('a'.repeat(151))).toBe(false)
    expect(lengthMet('a'.repeat(500))).toBe(false)
  })

  test('counts code points like the backend, not UTF-16 units', () => {
    // U+1D400 is one letter to Python's len() but has .length 2 here.
    const mathBold = '\u{1D400}'
    expect(lengthMet(mathBold.repeat(150))).toBe(true)
    expect(lengthMet(mathBold.repeat(151))).toBe(false)
  })

  test('an over-long username is not allMet', () => {
    expect(allMet(getUsernameRequirements('a'.repeat(151)))).toBe(false)
    expect(allMet(getUsernameRequirements('a'.repeat(150)))).toBe(true)
  })
})
