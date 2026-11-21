// Small helpers around the locally-persisted session, mirroring how the native
// clients read the signed-in user out of the keychain. The session token itself
// lives on the ApiClient; these helpers expose the current username/user id and
// clear everything on logout.
//
// Where the session is persisted depends on the "Remember Me" choice:
//   - remembered  -> localStorage   (survives browser restarts)
//   - not         -> sessionStorage (cleared when the tab/window closes, so the
//                                     session is ephemeral)
// Reads check both stores so callers don't need to know which one was used.

import { apiClient } from './client'
import { USERNAME_CHANGED_EVENT } from './sessionEvents'
import { parseFormerUsernames } from './formerUsernames'

// former_usernames: names this account gave up during the session (issue #594),
// one "name<TAB>held-until epoch ms" per line. See useOwnUsernames.
const SESSION_KEYS = ['session_token', 'user_id', 'username', 'former_usernames'] as const

function readSessionValue(key: string): string | null {
  return localStorage.getItem(key) ?? sessionStorage.getItem(key)
}

/**
 * Persists the signed-in session. When `rememberMe` is true the session is kept
 * in localStorage (survives browser restarts); otherwise it lives in
 * sessionStorage and is dropped when the tab/window closes. The session is
 * written to exactly one store so a previous choice can't linger.
 */
export function persistSession(
  session: { session_management_token: string; user_id: string; username?: string },
  rememberMe: boolean,
): void {
  const store = rememberMe ? localStorage : sessionStorage
  const other = rememberMe ? sessionStorage : localStorage
  store.setItem('session_token', session.session_management_token)
  store.setItem('user_id', session.user_id)
  // A fresh sign-in starts with no names given up.
  store.removeItem('former_usernames')
  if (session.username) {
    store.setItem('username', session.username)
  } else {
    // Don't let a username from a previous session linger in this store.
    store.removeItem('username')
  }
  SESSION_KEYS.forEach(key => other.removeItem(key))
}

export function getStoredSessionToken(): string | null {
  return readSessionValue('session_token')
}

export function getCurrentUsername(): string | null {
  return readSessionValue('username')
}

/** The server's `former_username` / `former_username_held_until` pair: the
 * name this account gave up whose hold is still running, and until when. */
export interface HeldFormerUsername {
  former_username?: string | null
  former_username_held_until?: string | null
}

/**
 * Replaces the cached username after a rename (issue #594), in whichever store
 * holds the session, so "is this me?" checks keep recognising the account. Also
 * used to refresh a name another device changed. No-op without a session.
 *
 * `held` is the server's report of which old name is still reserved for this
 * account, and until when. Only that exact, server-confirmed name is remembered
 * as the user's own — never the name this tab happened to have cached, which
 * after a missed rename elsewhere may already belong to someone else.
 */
export function updateStoredUsername(username: string, held?: HeldFormerUsername): void {
  for (const store of [localStorage, sessionStorage]) {
    if (store.getItem('session_token') !== null) {
      const previous = store.getItem('username')
      const previousFormer = store.getItem('former_usernames') ?? ''
      const now = Date.now()
      const former = parseFormerUsernames(previousFormer, now).filter(entry => entry.name !== username)
      const heldName = held?.former_username
      const heldUntil = held?.former_username_held_until ? Date.parse(held.former_username_held_until) : Number.NaN
      if (heldName && heldName !== username && Number.isFinite(heldUntil) && heldUntil > now) {
        const existing = former.find(entry => entry.name === heldName)
        if (existing) existing.heldUntil = heldUntil
        else former.push({ name: heldName, heldUntil })
      }
      const nextFormer = former.map(e => `${e.name}\t${e.heldUntil}`).join('\n')
      if (previous === username && nextFormer === previousFormer) return
      store.setItem('username', username)
      store.setItem('former_usernames', nextFormer)
      // Lets views that already read the old name re-render (useCurrentUsername).
      window.dispatchEvent(new Event(USERNAME_CHANGED_EVENT))
      return
    }
  }
}

export function getCurrentUserId(): string | null {
  return readSessionValue('user_id')
}

/** Clears the persisted session and the in-memory token (used by logout/delete). */
export function clearSession(): void {
  apiClient.setToken(null)
  SESSION_KEYS.forEach(key => {
    localStorage.removeItem(key)
    sessionStorage.removeItem(key)
  })
  clearRememberMeTokens()
}

// "Remember Me" tokens persisted across browser restarts so the app can rotate
// the session via the remember endpoint on startup (mirrors the native clients'
// WelcomeScreen auto-login).
//
// NOTE: localStorage matches the existing session-token storage but is readable
// by any script on the page (XSS-exposed). The hardened alternative is an
// httpOnly+Secure+SameSite cookie set by the backend, so JS can never read these
// long-lived credentials — that requires backend changes (the remember endpoint
// would read the cookie instead of the JSON body, plus CSRF protection).
const SERIES_IDENTIFIER_KEY = 'series_identifier'
const LOGIN_COOKIE_TOKEN_KEY = 'login_cookie_token'

export interface RememberMeTokens {
  seriesIdentifier: string
  loginCookieToken: string
}

export function saveRememberMeTokens(tokens: RememberMeTokens): void {
  localStorage.setItem(SERIES_IDENTIFIER_KEY, tokens.seriesIdentifier)
  localStorage.setItem(LOGIN_COOKIE_TOKEN_KEY, tokens.loginCookieToken)
}

export function loadRememberMeTokens(): RememberMeTokens | null {
  const seriesIdentifier = localStorage.getItem(SERIES_IDENTIFIER_KEY)
  const loginCookieToken = localStorage.getItem(LOGIN_COOKIE_TOKEN_KEY)
  if (!seriesIdentifier || !loginCookieToken) {
    // If either key is missing, treat any partial state as stale.
    clearRememberMeTokens()
    return null
  }
  return { seriesIdentifier, loginCookieToken }
}

export function clearRememberMeTokens(): void {
  localStorage.removeItem(SERIES_IDENTIFIER_KEY)
  localStorage.removeItem(LOGIN_COOKIE_TOKEN_KEY)
}
