import { describe, test, expect } from 'vitest'
import { extractTags, splitCaptionByTags, tagPathFor } from './tags'

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
})

describe('tagPathFor', () => {
  test('builds the tag route and encodes the tag', () => {
    expect(tagPathFor('sunset')).toBe('/tags/sunset')
    expect(tagPathFor('a b')).toBe('/tags/a%20b')
  })
})
