import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { apiClient } from './api/client'
import {
  clearRememberMeTokens,
  clearSession,
  getStoredSessionToken,
  loadRememberMeTokens,
  saveRememberMeTokens,
} from './api/session'
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
void refreshRememberMeSession()

// A banned account has its sessions revoked server-side; drop the local
// session and land on the login page, which explains the suspension.
apiClient.setOnAccountBanned(() => {
  clearSession()
  window.location.assign('/login?suspended=1')
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
