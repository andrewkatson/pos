import type { NotificationPreference } from './types'

/** A Settings → Notifications row, with how deep it sits in the type tree. */
export interface NotificationRow {
  pref: NotificationPreference
  depth: number
}

/**
 * The toggles to show, in order (issue #444). The backend sends the push types
 * as a tree — a master switch, a switch per kind, then one per relationship
 * source — with every parent before its children. A row is indented one level
 * under its parent and hidden while any ancestor is off, since an off parent
 * silences everything beneath it. A row whose parent is missing (an older
 * backend sends no `parent` at all) is shown at the top level.
 */
export function visibleNotificationRows(prefs: NotificationPreference[]): NotificationRow[] {
  const byType = new Map(prefs.map(p => [p.type, p]))
  const shownDepth = new Map<string, number>()
  const rows: NotificationRow[] = []
  for (const pref of prefs) {
    const parent = pref.parent ? byType.get(pref.parent) : undefined
    let depth = 0
    if (parent) {
      const parentDepth = shownDepth.get(parent.type)
      if (parentDepth === undefined || !parent.enabled) continue
      depth = parentDepth + 1
    }
    shownDepth.set(pref.type, depth)
    rows.push({ pref, depth })
  }
  return rows
}
