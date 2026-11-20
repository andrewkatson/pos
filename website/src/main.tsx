import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import App from './App'
import { apiClient } from './api/client'
import {
  clearRememberMeTokens,
  getStoredSessionToken,
  loadRememberMeTokens,
  saveRememberMeTokens,
  updateStoredUsername,
} from './api/session'
import { registerForPush } from './push/webPush'
import { installAuthFailureHandlers } from './api/authFailureRedirects'
import './index.css'

// Restore the session token persisted at login so a page reload keeps the user
// authenticated (the ApiClient otherwise only holds the token in memory). The
// token lives in localStorage for "remember me" sessions and sessionStorage
// otherwise; getStoredSessionToken checks both.
const storedToken = getStoredSessionToken()
if (storedToken) {
  apiClient.setToken(storedToken)
}

// If the user chose "Remember Me", rotate the session + cookie tokens on startup
// so the login survives across browser restarts (parity with the native clients'
// WelcomeScreen auto-login). Remember-me tokens only ever accompany a persistent
// (localStorage) session, so we read the session token straight from localStorage
// — never from an ephemeral sessionStorage session, which we must not silently
// upgrade to persistent. Best-effort and non-blocking: on any inconsistency or
// failure we drop the stale remember-me tokens and fall back to the existing
// session.
async function refreshRememberMeSession(): Promise<void> {
  const tokens = loadRememberMeTokens()
  if (!tokens) return
  const rememberedToken = localStorage.getItem('session_token')
  if (!rememberedToken) {
    // Tokens with no matching persistent session — stale, so drop them.
    clearRememberMeTokens()
    return
  }
  try {
    const result = await apiClient.loginWithRememberMe({
      session_management_token: rememberedToken,
      series_identifier: tokens.seriesIdentifier,
      login_cookie_token: tokens.loginCookieToken,
    })
    localStorage.setItem('session_token', result.session_management_token)
    // The remembered session lives only in localStorage; make sure no stray
    // ephemeral copies can shadow it.
    sessionStorage.removeItem('session_token')
    sessionStorage.removeItem('user_id')
    sessionStorage.removeItem('username')
    saveRememberMeTokens({
      seriesIdentifier: tokens.seriesIdentifier,
      loginCookieToken: result.login_cookie_token,
    })
  } catch {
    clearRememberMeTokens()
  }
}
// A banned account has its sessions revoked server-side, and an unverified
// email blocks every authenticated endpoint, so a restored session that hits
// either is useless: drop it and land on the login page, which explains why.
// Public pages (the support and legal URLs) are the exception and stay put —
// see api/authFailureRedirects.ts.
installAuthFailureHandlers({
  pathname: () => window.location.pathname,
  assign: url => window.location.assign(url),
})

// Refresh a remembered session, then (whether or not it rotated) refresh this
// browser's push token if we're signed in. promptIfNeeded is left false so a
// returning user isn't asked for notification permission on every load — that
// prompt happens at login. Best-effort; never blocks startup.
//
// This runs on every load, public pages included. Registration is the only
// thing that subscribes this tab to foreground messages, and the rest of the
// app is reached from here by client-side navigation that never re-runs it —
// so a signed-in user whose first load happened to be /support or a legal page
// would browse on with notifications silently dead. Doing the work everywhere
// also means a session that has since been suspended is cleared promptly
// rather than lingering in storage; what must not happen on these pages is the
// *redirect*, and that is handled above.
//
// The cached username is refreshed too: another device may have renamed the
// account (issue #594), and "is this me?" checks compare against the cache.
// The old name keeps resolving for a while, so a stale cache is not urgent.
void refreshRememberMeSession().finally(() => {
  void registerForPush()
  if (getStoredSessionToken()) {
    apiClient
      .getCurrentUser()
      .then(user => updateStoredUsername(user.username))
      .catch(() => {
        // Best-effort; an auth failure is handled by the handlers above.
      })
  }
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
