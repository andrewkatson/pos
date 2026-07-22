import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Logo from '../components/Logo'
import {
  ACCOUNT_BANNED,
  ACCOUNT_SUSPENDED_MESSAGE,
  EMAIL_NOT_VERIFIED,
  EMAIL_NOT_VERIFIED_MESSAGE,
  INVALID_TWO_FACTOR_CHALLENGE,
  apiClient,
} from '../api/client'
import type { ApiError } from '../api/client'
import type { AuthResponse } from '../api/types'
import { isTwoFactorRequired } from '../api/types'
import {
  clearRememberMeTokens,
  clearSession,
  persistSession,
  saveRememberMeTokens,
} from '../api/session'
import './LoginPage.css'

function LoginPage() {
  const navigate = useNavigate()
  // Set when a session was force-cleared and the user was redirected here
  // (see main.tsx): a banned account, or one whose email is unverified.
  const [searchParams] = useSearchParams()
  const [usernameOrEmail, setUsernameOrEmail] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(
    searchParams.has('suspended')
      ? ACCOUNT_SUSPENDED_MESSAGE
      : searchParams.has('verify_email')
        ? EMAIL_NOT_VERIFIED_MESSAGE
        : null,
  )
  const [isLoading, setIsLoading] = useState(false)

  // Two-factor step. Set when login answered with a challenge instead of a
  // session; the login form is replaced by the code-entry step until the
  // challenge is exchanged (or the user goes back).
  const [challengeToken, setChallengeToken] = useState<string | null>(null)
  const [twoFactorCode, setTwoFactorCode] = useState('')
  const [useRecoveryCode, setUseRecoveryCode] = useState(false)

  const isFormValid = usernameOrEmail.trim().length > 0 && password.length > 0
  // Authenticator codes are 6 digits; recovery codes are 10 hex characters
  // (backend/user_system/constants.py Patterns).
  const isCodeValid = useRecoveryCode
    ? /^[0-9a-fA-F]{10}$/.test(twoFactorCode.trim())
    : /^\d{6}$/.test(twoFactorCode.trim())

  /** Shared tail of both login steps: persist the session and enter the app. */
  function completeLogin(response: AuthResponse) {
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
  }

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
      if (isTwoFactorRequired(response)) {
        // Password accepted, but the account needs its second factor. Drop any
        // persisted session and remember-me tokens too: no session has been
        // issued for this attempt, and leaving them would let a reload on the
        // 2FA step restore the old one and appear signed in.
        clearSession()
        setChallengeToken(response.challenge_token)
        setErrorMessage(null)
        return
      }
      completeLogin(response)
    } catch (err) {
      const apiErr = err as ApiError
      if (apiErr.message === ACCOUNT_BANNED) {
        setErrorMessage(ACCOUNT_SUSPENDED_MESSAGE)
      } else if (apiErr.message === EMAIL_NOT_VERIFIED) {
        setErrorMessage(EMAIL_NOT_VERIFIED_MESSAGE)
      } else {
        setErrorMessage(apiErr.message ?? 'Login failed. Please check your credentials.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  async function handleTwoFactorSubmit(e: FormEvent) {
    e.preventDefault()
    // Guard against re-entry while a request is already in flight, and clear
    // any stale error banner as the new attempt starts.
    if (!challengeToken || !isCodeValid || isLoading) return
    setErrorMessage(null)
    setIsLoading(true)
    try {
      const code = twoFactorCode.trim()
      const response = await apiClient.loginWithTwoFactor(
        useRecoveryCode
          ? { challenge_token: challengeToken, recovery_code: code.toLowerCase() }
          : { challenge_token: challengeToken, totp_code: code },
      )
      completeLogin(response)
    } catch (err) {
      const apiErr = err as ApiError
      if (apiErr.message === INVALID_TWO_FACTOR_CHALLENGE) {
        // The challenge timed out (or was invalidated): start over from the
        // default authenticator-code entry, matching backToLogin().
        setChallengeToken(null)
        setTwoFactorCode('')
        setUseRecoveryCode(false)
        setErrorMessage('Your login expired. Please sign in again.')
      } else {
        setErrorMessage(apiErr.message ?? 'Verification failed. Please try again.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  function backToLogin() {
    setChallengeToken(null)
    setTwoFactorCode('')
    setUseRecoveryCode(false)
    setErrorMessage(null)
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <button
          type="button"
          className="auth-back"
          disabled={isLoading}
          onClick={() => (challengeToken ? backToLogin() : navigate('/'))}
          aria-label={challengeToken ? 'Back to login' : 'Back to home'}
        >
          ← Back
        </button>

        <div className="auth-logo">
          <Logo size={80} />
        </div>

        <h1 className="auth-title">{challengeToken ? 'Two-Factor Authentication' : 'Login'}</h1>

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

        {challengeToken ? (
          <form className="auth-form" onSubmit={handleTwoFactorSubmit} noValidate>
            <p className="auth-instructions">
              {useRecoveryCode
                ? 'Enter one of your recovery codes. Each code works only once.'
                : 'Enter the 6-digit code from your authenticator app.'}
            </p>

            <div className="auth-field">
              <label className="auth-label" htmlFor="twoFactorCode">
                {useRecoveryCode ? 'Recovery Code' : 'Authenticator Code'}
              </label>
              <input
                id="twoFactorCode"
                className="auth-input"
                type="text"
                inputMode={useRecoveryCode ? 'text' : 'numeric'}
                autoComplete="one-time-code"
                autoCapitalize="none"
                maxLength={useRecoveryCode ? 10 : 6}
                value={twoFactorCode}
                onChange={e => setTwoFactorCode(e.target.value)}
                disabled={isLoading}
              />
            </div>

            {isLoading ? (
              <div className="auth-spinner" aria-label="Verifying…">
                <span className="spinner" />
              </div>
            ) : (
              <button type="submit" className="auth-button" disabled={!isCodeValid}>
                Verify
              </button>
            )}

            <button
              type="button"
              className="auth-link auth-link--right"
              disabled={isLoading}
              onClick={() => {
                setUseRecoveryCode(v => !v)
                setTwoFactorCode('')
              }}
            >
              {useRecoveryCode ? 'Use an authenticator code instead' : 'Use a recovery code instead'}
            </button>
          </form>
        ) : (
          <>
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
          </>
        )}
      </div>
    </div>
  )
}

export default LoginPage
