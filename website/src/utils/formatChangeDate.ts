/** "March 3, 2027" for an ISO time, or null if there is none or it is
 * unparseable — e.g. when the next username change is allowed (issue #594). */
export function formatChangeDate(iso: string | null | undefined): string | null {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })
}
