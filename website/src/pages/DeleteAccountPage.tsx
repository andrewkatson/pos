import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
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
import { isTwoFactorRequired } from '../api/types'
import { clearSession, getStoredSessionToken } from '../api/session'
import './LoginPage.css'
import './DeleteAccountPage.css'

/**
 * Public, unauthenticated-reachable account & data deletion page, served at
 * /delete-account (issue #439). Google Play requires a stable web URL where a
 * user can request that their account and associated data be deleted, so this
 * page stands alone rather than living behind the in-app Settings tab.
 *
 * Flow:
 *   1. `auth`    — if no session is present, the user signs in here (username /
 *                  email + password, plus a two-factor step for enrolled
 *                  accounts). A session restored on page load (main.tsx) skips
 *                  straight to the confirmation step.
 *   2. `confirm` — the account and everything tied to it is listed, and an
 *                  explicit acknowledgement gates the permanent delete.
 *   3. `done`    — the account is gone and the local session is cleared.
 *
 * The actual deletion reuses `POST /user/delete/` (apiClient.deleteAccount),
 * the same endpoint the Settings tab and native clients use, which cascades to
 * the user's posts, comments, likes, saved posts, appeals, follows, blocks, and
 * images.
 */
type Step = 'auth' | 'confirm' | 'done'

function DeleteAccountPage() {
  const navigate = useNavigate()

  // Start on the confirmation step when a session was restored on load
  // (main.tsx puts the persisted token back on the client); otherwise sign in.
  const [step, setStep] = useState<Step>(() =>
    getStoredSessionToken() ? 'confirm' : 'auth',
  )

  const [usernameOrEmail, setUsernameOrEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  // Two-factor step, mirroring LoginPage: login can answer with a challenge
  // instead of a session, which is exchanged (with a code) for the real session.
  const [challengeToken, setChallengeToken] = useState<string | null>(null)
  const [twoFactorCode, setTwoFactorCode] = useState('')
  const [useRecoveryCode, setUseRecoveryCode] = useState(false)

  // Final acknowledgement guard so the permanent action can't be a stray click.
  const [acknowledged, setAcknowledged] = useState(false)

  const isFormValid = usernameOrEmail.trim().length > 0 && password.length > 0
  const isCodeValid = useRecoveryCode
    ? /^[0-9a-fA-F]{10}$/.test(twoFactorCode.trim())
    : /^\d{6}$/.test(twoFactorCode.trim())

  async function handleLogin(e: FormEvent) {
    e.preventDefault()
    if (!isFormValid || isLoading) return
    setIsLoading(true)
    try {
      // No remember-me: deletion is a one-off action, so we never persist a
      // long-lived credential here — the in-memory session token is enough.
      const response = await apiClient.login({
        username_or_email: usernameOrEmail.trim(),
        password,
        remember_me: false,
      })
      if (isTwoFactorRequired(response)) {
        setChallengeToken(response.challenge_token)
        setErrorMessage(null)
        return
      }
      setErrorMessage(null)
      setStep('confirm')
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
    if (!challengeToken || !isCodeValid || isLoading) return
    setErrorMessage(null)
    setIsLoading(true)
    try {
      const code = twoFactorCode.trim()
      await apiClient.loginWithTwoFactor(
        useRecoveryCode
          ? { challenge_token: challengeToken, recovery_code: code.toLowerCase() }
          : { challenge_token: challengeToken, totp_code: code },
      )
      // Drop the challenge state now that it's exchanged for a session, so the
      // confirmation step's Back button doesn't behave as if we're still in the
      // 2FA step.
      backToLogin()
      setStep('confirm')
    } catch (err) {
      const apiErr = err as ApiError
      if (apiErr.message === INVALID_TWO_FACTOR_CHALLENGE) {
        backToLogin()
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

  async function handleDelete() {
    if (!acknowledged || isLoading) return
    setErrorMessage(null)
    setIsLoading(true)
    try {
      await apiClient.deleteAccount()
      clearSession()
      setStep('done')
    } catch (err) {
      const apiErr = err as ApiError
      setErrorMessage(apiErr.message ?? 'Failed to delete your account. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        {step !== 'done' && (
          <button
            type="button"
            className="auth-back"
            disabled={isLoading}
            onClick={() => (challengeToken ? backToLogin() : navigate('/'))}
            aria-label={challengeToken ? 'Back to sign in' : 'Back to home'}
          >
            ← Back
          </button>
        )}

        <div className="auth-logo">
          <Logo size={80} />
        </div>

        <h1 className="auth-title">Delete Account &amp; Data</h1>

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

        {step === 'auth' &&
          (challengeToken ? (
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
                {useRecoveryCode
                  ? 'Use an authenticator code instead'
                  : 'Use a recovery code instead'}
              </button>
            </form>
          ) : (
            <>
              <p className="auth-instructions">
                Sign in to the account you want to delete. We verify your identity
                first so no one else can delete your account.
              </p>
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

                {isLoading ? (
                  <div className="auth-spinner" aria-label="Signing in…">
                    <span className="spinner" />
                  </div>
                ) : (
                  <button type="submit" className="auth-button" disabled={!isFormValid}>
                    Continue
                  </button>
                )}
              </form>
            </>
          ))}

        {step === 'confirm' && (
          <>
            <p className="auth-instructions">
              Deleting your account is <strong>permanent and cannot be undone</strong>.
              Everything below is removed right away:
            </p>
            <ul className="delete-account__list">
              <li>Your profile, username, email, and bio</li>
              <li>All of your posts and their images</li>
              <li>Your comments and replies</li>
              <li>Your likes and saved posts</li>
              <li>Your appeals</li>
              <li>Who you follow and who follows you, and your blocks</li>
              <li>Your login sessions and remembered devices</li>
            </ul>

            <label className="delete-account__ack">
              <input
                type="checkbox"
                checked={acknowledged}
                onChange={e => setAcknowledged(e.target.checked)}
                disabled={isLoading}
              />
              <span>I understand this permanently deletes my account and data.</span>
            </label>

            {isLoading ? (
              <div className="auth-spinner" aria-label="Deleting your account…">
                <span className="spinner" />
              </div>
            ) : (
              <button
                type="button"
                className="delete-account__danger-button"
                disabled={!acknowledged}
                onClick={handleDelete}
              >
                Delete my account and data
              </button>
            )}

            <button
              type="button"
              className="auth-link"
              disabled={isLoading}
              onClick={() => navigate('/')}
            >
              Cancel
            </button>
          </>
        )}

        {step === 'done' && (
          <>
            <p className="auth-instructions">
              Your account and all associated data have been permanently deleted.
              We're sorry to see you go.
            </p>
            <Link to="/" className="auth-button delete-account__home-link">
              Return home
            </Link>
          </>
        )}
      </div>
    </div>
  )
}

export default DeleteAccountPage
