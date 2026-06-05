// Small helpers around the locally-persisted session, mirroring how the native
// clients read the signed-in user out of the keychain. The session token itself
// lives on the ApiClient (and in localStorage for reload survival); these helpers
// expose the current username/user id and clear everything on logout.

import { apiClient } from './client'

export function getCurrentUsername(): string | null {
  return localStorage.getItem('username')
}

export function getCurrentUserId(): string | null {
  return localStorage.getItem('user_id')
}

/** Clears the persisted session and the in-memory token (used by logout/delete). */
export function clearSession(): void {
  apiClient.setToken(null)
  localStorage.removeItem('session_token')
  localStorage.removeItem('user_id')
  localStorage.removeItem('username')
}
