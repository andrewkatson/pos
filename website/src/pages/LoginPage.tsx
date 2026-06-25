import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Logo from '../components/Logo'
import { ACCOUNT_BANNED, ACCOUNT_SUSPENDED_MESSAGE, apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import { clearRememberMeTokens, persistSession, saveRememberMeTokens } from '../api/session'
import './LoginPage.css'

function LoginPage() {
  const navigate = useNavigate()
  // Set when a banned account's session was force-cleared and the user was
  // redirected here (see main.tsx).
  const [searchParams] = useSearchParams()
  const [usernameOrEmail, setUsernameOrEmail] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(
    searchParams.has('suspended') ? ACCOUNT_SUSPENDED_MESSAGE : null,
  )

  const isFormValid = usernameOrEmail.trim().length > 0 && password.length > 0

  async function handleLogin(e: FormEvent) {
    e.preventDefault()
    if (!isFormValid) return
    setIsLoading(true)
    try {
      const response = await apiClient.login({
        username_or_email: usernameOrEmail.trim(),
        password,
        remember_me: rememberMe,
      })
      // When "Remember Me" is off the session goes to sessionStorage and is
      // cleared when the browser/tab closes; when on it persists in localStorage.
      persistSession(response, rememberMe)
      // Persist the remember-me tokens (only returned when remember_me was
      // requested) so the session can be rotated on the next browser start;
      // otherwise drop any stale tokens from a previous "remember me" login.
      if (rememberMe && response.series_identifier && response.login_cookie_token) {
        saveRememberMeTokens({
          seriesIdentifier: response.series_identifier,
          loginCookieToken: response.login_cookie_token,
        })
      } else {
        clearRememberMeTokens()
      }
      navigate('/home')
    } catch (err) {
      const apiErr = err as ApiError
      if (apiErr.message === ACCOUNT_BANNED) {
        setErrorMessage(ACCOUNT_SUSPENDED_MESSAGE)
      } else {
        setErrorMessage(apiErr.message ?? 'Login failed. Please check your credentials.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <button
          type="button"
          className="auth-back"
          onClick={() => navigate('/')}
          aria-label="Back to home"
        >
          ← Back
        </button>

        <div className="auth-logo">
          <Logo size={80} />
        </div>

        <h1 className="auth-title">Login</h1>

        {errorMessage && (
          <div className="auth-error" role="alert">
            <p>{errorMessage}</p>
            <button
              type="button"
              className="auth-error__dismiss"
              aria-label="Dismiss error"
              onClick={() => setErrorMessage(null)}
            >
              ✕
            </button>
          </div>
        )}

        <form className="auth-form" onSubmit={handleLogin} noValidate>
          <div className="auth-field">
            <label className="auth-label" htmlFor="usernameOrEmail">
              Username or Email
            </label>
            <input
              id="usernameOrEmail"
              className="auth-input"
              type="text"
              inputMode="email"
              autoComplete="username"
              autoCapitalize="none"
              value={usernameOrEmail}
              onChange={e => setUsernameOrEmail(e.target.value)}
              disabled={isLoading}
            />
          </div>

          <div className="auth-field">
            <label className="auth-label" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              className="auth-input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              disabled={isLoading}
            />
          </div>

          <div className="auth-toggle-row">
            <span className="auth-label">Remember Me</span>
            <label className="toggle" aria-label="Remember me">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={e => setRememberMe(e.target.checked)}
                disabled={isLoading}
              />
              <span className="toggle__track" />
            </label>
          </div>

          {isLoading ? (
            <div className="auth-spinner" aria-label="Logging in…">
              <span className="spinner" />
            </div>
          ) : (
            <button
              type="submit"
              className="auth-button"
              disabled={!isFormValid}
            >
              Login
            </button>
          )}
        </form>

        <button
          type="button"
          className="auth-link auth-link--right"
          onClick={() => navigate('/request-reset')}
        >
          Forgot Password?
        </button>
      </div>
    </div>
  )
}

export default LoginPage
