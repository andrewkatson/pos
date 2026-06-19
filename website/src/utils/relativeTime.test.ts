import { describe, expect, test } from 'vitest'
import { formatRelativeTime } from './relativeTime'

// Fixed reference point so the assertions don't depend on the wall clock.
const now = new Date('2026-06-19T12:00:00Z')

function ago(seconds: number): Date {
  return new Date(now.getTime() - seconds * 1000)
}

const MIN = 60
const HOUR = 60 * MIN
const DAY = 24 * HOUR
const WEEK = 7 * DAY
const YEAR = 365 * DAY

describe('formatRelativeTime', () => {
  test('collapses sub-minute durations to "< 1 min"', () => {
    expect(formatRelativeTime(ago(0), now)).toBe('< 1 min')
    expect(formatRelativeTime(ago(1), now)).toBe('< 1 min')
    expect(formatRelativeTime(ago(59), now)).toBe('< 1 min')
  })

  test('future or equal timestamps read "< 1 min" rather than negative', () => {
    expect(formatRelativeTime(new Date(now.getTime() + 5000), now)).toBe('< 1 min')
  })

  test('rounds down to whole minutes', () => {
    expect(formatRelativeTime(ago(MIN), now)).toBe('1 min')
    expect(formatRelativeTime(ago(MIN + 59), now)).toBe('1 min')
    expect(formatRelativeTime(ago(59 * MIN), now)).toBe('59 min')
  })

  test('rounds down to whole hours', () => {
    expect(formatRelativeTime(ago(HOUR), now)).toBe('1 hr')
    expect(formatRelativeTime(ago(23 * HOUR), now)).toBe('23 hr')
  })

  test('rounds down to whole days with pluralization', () => {
    expect(formatRelativeTime(ago(DAY), now)).toBe('1 day')
    expect(formatRelativeTime(ago(6 * DAY), now)).toBe('6 days')
  })

  test('rounds down to whole weeks with pluralization', () => {
    expect(formatRelativeTime(ago(WEEK), now)).toBe('1 week')
    expect(formatRelativeTime(ago(8 * WEEK), now)).toBe('8 weeks')
    // 364 days is still under a year, so it stays in weeks.
    expect(formatRelativeTime(ago(364 * DAY), now)).toBe('52 weeks')
  })

  test('rounds down to whole years with pluralization', () => {
    expect(formatRelativeTime(ago(YEAR), now)).toBe('1 year')
    expect(formatRelativeTime(ago(2 * YEAR + 5 * DAY), now)).toBe('2 years')
  })

  test('accepts ISO strings and returns "" for unparseable input', () => {
    expect(formatRelativeTime(ago(5 * MIN).toISOString(), now)).toBe('5 min')
    expect(formatRelativeTime('not a date', now)).toBe('')
  })
})
