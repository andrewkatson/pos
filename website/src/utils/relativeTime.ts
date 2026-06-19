/**
 * Formats how long ago `from` happened, relative to `now` (defaults to the
 * current time).
 *
 * Sub-minute durations collapse to "< 1 min" so the label never displays a
 * second-level granularity that ticks on every render. Larger durations round
 * down to the largest whole unit: minutes, hours, days, weeks, then years.
 * This mirrors the same helper on iOS (`RelativeTime`) and Android
 * (`RelativeTime`) so the three clients read identically.
 *
 * Returns an empty string when `from` can't be parsed into a date.
 */
export function formatRelativeTime(from: Date | string, now: Date = new Date()): string {
  const fromMs = typeof from === 'string' ? Date.parse(from) : from.getTime()
  if (Number.isNaN(fromMs)) return ''

  const seconds = Math.max(0, Math.floor((now.getTime() - fromMs) / 1000))
  if (seconds < 60) return '< 1 min'

  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} min`

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hr`

  const days = Math.floor(hours / 24)
  if (days < 7) return `${days} ${days === 1 ? 'day' : 'days'}`

  if (days < 365) {
    const weeks = Math.floor(days / 7)
    return `${weeks} ${weeks === 1 ? 'week' : 'weeks'}`
  }

  const years = Math.floor(days / 365)
  return `${years} ${years === 1 ? 'year' : 'years'}`
}
