import { expect, test } from 'vitest'
import { savedEditIsNewer } from './editedTime'

test('a saved edit beats a fetch that predates it (#462)', () => {
  expect(savedEditIsNewer('2024-01-02T00:00:00Z', null)).toBe(true)
  expect(savedEditIsNewer('2024-01-02T00:00:00Z', '2024-01-01T00:00:00Z')).toBe(true)
})

test('a fetch at least as new as the saved edit wins (#462)', () => {
  expect(savedEditIsNewer('2024-01-02T00:00:00Z', '2024-01-02T00:00:00Z')).toBe(false)
  expect(savedEditIsNewer('2024-01-02T00:00:00Z', '2024-01-03T00:00:00Z')).toBe(false)
  expect(savedEditIsNewer(null, null)).toBe(false)
})
