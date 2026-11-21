import { useMemo, useSyncExternalStore } from 'react'
import { getCurrentUsername } from './session'
import { USERNAME_CHANGED_EVENT } from './sessionEvents'

function subscribe(onChange: () => void): () => void {
  window.addEventListener(USERNAME_CHANGED_EVENT, onChange)
  // Another tab renaming the account writes localStorage, which fires `storage`
  // here.
  window.addEventListener('storage', onChange)
  return () => {
    window.removeEventListener(USERNAME_CHANGED_EVENT, onChange)
    window.removeEventListener('storage', onChange)
  }
}

/**
 * The signed-in username, re-rendering when it changes (issue #594). Views that
 * decide "is this mine?" use this rather than reading the cache once, so a
 * rename — including one from another device, picked up by the startup
 * refresh after the view mounted — updates their owner controls.
 */
export function useCurrentUsername(): string | null {
  return useSyncExternalStore(subscribe, getCurrentUsername, () => null)
}

/** Read straight from storage (not through api/session) so tests that mock
 * that module with only getCurrentUsername keep working. */
function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key) ?? sessionStorage.getItem(key)
  } catch {
    return null
  }
}

/** Current username plus the names given up this session (written by
 * updateStoredUsername), newline-separated: a stable string snapshot. */
function ownUsernamesKey(): string {
  const current = getCurrentUsername()
  if (!current) return ''
  const former = readStored('former_usernames') ?? ''
  return former ? `${current}\n${former}` : current
}

/**
 * Every name the signed-in account answers to — current plus those given up
 * this session (issue #594) — for deciding whether a post or comment is the
 * user's own. Cached rows still carry the author name they were fetched with,
 * and a load can finish with the name it started with; counting the account's
 * former names keeps both right without refetching. Empty when signed out.
 */
export function useOwnUsernames(): readonly string[] {
  const key = useSyncExternalStore(subscribe, ownUsernamesKey, () => '')
  return useMemo(() => (key ? key.split('\n') : []), [key])
}
