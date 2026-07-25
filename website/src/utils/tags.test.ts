import { describe, test, expect } from 'vitest'
import { extractTags, MAX_TAG_LENGTH, MAX_TAGS_PER_POST, splitCaptionByTags, tagPathFor } from './tags'

describe('extractTags', () => {
  test('returns empty for a caption with no tags', () => {
    expect(extractTags('just a plain caption')).toEqual([])
  })

  test('returns empty for an empty string', () => {
    expect(extractTags('')).toEqual([])
  })

  test('extracts a single tag', () => {
    expect(extractTags('what a #sunset')).toEqual(['sunset'])
  })

  test('lowercases and de-duplicates, keeping first-seen order', () => {
    expect(extractTags('#Beach then #sunset then #BEACH')).toEqual(['beach', 'sunset'])
  })

  test('stops a tag at punctuation', () => {
    expect(extractTags('great #day! and #ok.')).toEqual(['day', 'ok'])
  })

  test('includes digits and underscores', () => {
    expect(extractTags('#a_1 and #2024')).toEqual(['a_1', '2024'])
  })

  test('a bare # is not a tag', () => {
    expect(extractTags('a # b #real')).toEqual(['real'])
  })

  test('skips overlong tags but keeps valid ones', () => {
    const long = 'a'.repeat(MAX_TAG_LENGTH + 1)
    expect(extractTags(`#${long} #ok`)).toEqual(['ok'])
  })

  test('caps the number of tags at MAX_TAGS_PER_POST', () => {
    const caption = Array.from({ length: MAX_TAGS_PER_POST + 5 }, (_, i) => `#t${i}`).join(' ')
    expect(extractTags(caption)).toHaveLength(MAX_TAGS_PER_POST)
  })
})

describe('splitCaptionByTags', () => {
  test('splits a caption into text and tag segments', () => {
    expect(splitCaptionByTags('a #sun b')).toEqual([
      { type: 'text', text: 'a ' },
      { type: 'tag', text: '#sun', tag: 'sun' },
      { type: 'text', text: ' b' },
    ])
  })

  test('normalizes the tag but preserves the original text', () => {
    expect(splitCaptionByTags('#SunSet')).toEqual([
      { type: 'tag', text: '#SunSet', tag: 'sunset' },
    ])
  })

  test('returns a single text segment when there are no tags', () => {
    expect(splitCaptionByTags('no tags here')).toEqual([
      { type: 'text', text: 'no tags here' },
    ])
  })

  test('leaves an overlong #token as plain text (never links a non-storable tag)', () => {
    const long = 'a'.repeat(MAX_TAG_LENGTH + 1)
    const segments = splitCaptionByTags(`#${long} #ok`)
    // The overlong token stays in a text run; only #ok becomes a tag.
    expect(segments.some(s => s.type === 'tag' && s.tag === 'ok')).toBe(true)
    expect(segments.some(s => s.type === 'tag' && s.tag === long)).toBe(false)
    expect(segments.map(s => s.text).join('')).toContain(`#${long}`)
  })

  test('does not linkify unique tags past the cap', () => {
    const caption = Array.from({ length: MAX_TAGS_PER_POST + 1 }, (_, i) => `#t${i}`).join(' ')
    const tagSegments = splitCaptionByTags(caption).filter(s => s.type === 'tag')
    expect(tagSegments).toHaveLength(MAX_TAGS_PER_POST)
  })
})

describe('tagPathFor', () => {
  test('builds the tag route and encodes the tag', () => {
    expect(tagPathFor('sunset')).toBe('/tags/sunset')
    expect(tagPathFor('a b')).toBe('/tags/a%20b')
  })
})
