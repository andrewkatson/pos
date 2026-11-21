import { useSyncExternalStore } from 'react'
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
