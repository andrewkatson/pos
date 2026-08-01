import { test, expect } from 'vitest'
import {
  INTEREST_OPTIONS,
  INTEREST_SLUGS,
  parseFreeformInput,
  matchInterestSlugs,
} from './interestVocabulary'

test('vocabulary slugs are unique and non-empty', () => {
  const slugs = INTEREST_OPTIONS.map(o => o.slug)
  expect(new Set(slugs).size).toBe(slugs.length)
  expect(slugs.every(s => s.length > 0)).toBe(true)
  expect(INTEREST_SLUGS.size).toBe(slugs.length)
})

test('parseFreeformInput splits comma lists, trims, and drops empties', () => {
  expect(parseFreeformInput('hiking, jazz ,  baking')).toEqual(['hiking', 'jazz', 'baking'])
  expect(parseFreeformInput('  , ,')).toEqual([])
  expect(parseFreeformInput('solo')).toEqual(['solo'])
})

test('parseFreeformInput dedupes case-insensitively, preserving first', () => {
  expect(parseFreeformInput('Nature, nature, NATURE')).toEqual(['Nature'])
})

test('matchInterestSlugs maps a term to bucket slugs by word', () => {
  expect(matchInterestSlugs('a walk in nature with music')).toEqual(['nature', 'music'])
  expect(matchInterestSlugs('hiking trip')).toEqual([])
})
