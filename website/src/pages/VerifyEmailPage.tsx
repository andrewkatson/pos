import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Logo from '../components/Logo'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import './LoginPage.css'

type VerifyState = 'missing-token' | 'verifying' | 'success' | 'error'

// Landing page for the verification link in the welcome email
// (https://smiling.social/verify-email?token=...). Verifies automatically on
// load; on failure (expired/used token) it offers to resend the email.
function VerifyEmailPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')

  const [state, setState] = useState<VerifyState>(token ? 'verifying' : 'missing-token')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [usernameOrEmail, setUsernameOrEmail] = useState('')
  const [resendMessage, setResendMessage] = useState<string | null>(null)
  const [isResending, setIsResending] = useState(false)

  // The token is single-use, so guard against the effect firing twice
  // (e.g. React StrictMode) and the second call reporting a false failure.
  const hasRequested = useRef(false)

  useEffect(() => {
    if (!token || hasRequested.current) return
    hasRequested.current = true
    apiClient
      .verifyEmail({ verification_token: token })
      .then(() => setState('success'))
      .catch((err: ApiError) => {
        setErrorMessage(err.message ?? 'Verification failed. The link may have expired.')
        setState('error')
      })
  }, [token])

  async function handleResend(e: FormEvent) {
    e.preventDefault()
    if (usernameOrEmail.trim().length === 0) return
    setIsResending(true)
    setResendMessage(null)
    try {
      await apiClient.resendVerificationEmail({ username_or_email: usernameOrEmail.trim() })
      setResendMessage('A new verification email is on its way. Check your inbox.')
    } catch (err) {
      const apiErr = err as ApiError
      setResendMessage(apiErr.message ?? 'Could not resend the email. Please try again.')
    } finally {
      setIsResending(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <Logo size={80} />
        </div>

        <h1 className="auth-title">Email Verification</h1>

        {state === 'verifying' && (
          <div className="auth-spinner" aria-label="Verifying…">
            <span className="spinner" />
          </div>
        )}

        {state === 'success' && (
          <>
            <p style={{ color: 'rgba(255,255,255,0.8)', textAlign: 'center', lineHeight: 1.5, margin: 0 }}>
              Your email address has been verified. You can now log in.
            </p>
            <button type="button" className="auth-button" onClick={() => navigate('/login')}>
              Go to Login
            </button>
          </>
        )}

        {state === 'missing-token' && (
          <p style={{ color: 'rgba(255,255,255,0.8)', textAlign: 'center', lineHeight: 1.5, margin: 0 }}>
            This page verifies your email address, but the link is missing its token. Please open
            the verification link from your welcome email.
          </p>
        )}

        {state === 'error' && (
          <>
            {errorMessage && (
              <div className="auth-error" role="alert">
                <p>{errorMessage}</p>
              </div>
            )}
            <p style={{ color: 'rgba(255,255,255,0.8)', textAlign: 'center', lineHeight: 1.5, margin: 0 }}>
              Enter your username or email below and we&apos;ll send you a fresh verification link.
            </p>
            <form className="auth-form" onSubmit={handleResend} noValidate>
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
                  disabled={isResending}
                />
              </div>
              {resendMessage && (
                <p style={{ color: 'rgba(255,255,255,0.8)', textAlign: 'center', margin: 0 }} role="status">
                  {resendMessage}
                </p>
              )}
              {isResending ? (
                <div className="auth-spinner" aria-label="Resending…">
                  <span className="spinner" />
                </div>
              ) : (
                <button
                  type="submit"
                  className="auth-button"
                  disabled={usernameOrEmail.trim().length === 0}
                >
                  Resend Verification Email
                </button>
              )}
            </form>
          </>
        )}

        {state !== 'success' && (
          <button
            type="button"
            className="auth-link auth-link--right"
            onClick={() => navigate('/login')}
          >
            Back to Login
          </button>
        )}
      </div>
    </div>
  )
}

export default VerifyEmailPage
