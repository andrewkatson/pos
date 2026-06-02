import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate, useLocation } from 'react-router-dom'
import Logo from '../components/Logo'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import './LoginPage.css'

function VerifyResetPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const usernameOrEmail =
    (location.state as { usernameOrEmail?: string } | null)?.usernameOrEmail ?? ''

  const [verificationToken, setVerificationToken] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  if (!usernameOrEmail) {
    return <Navigate to="/request-reset" replace />
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (verificationToken.trim().length === 0) return
    setIsLoading(true)
    try {
      const response = await apiClient.verifyReset({
        username_or_email: usernameOrEmail.trim(),
        verification_token: verificationToken.trim(),
      })
      setErrorMessage(null)
      navigate('/reset-password', {
        state: { usernameOrEmail: usernameOrEmail.trim(), resetToken: response.reset_token },
      })
    } catch (err) {
      const apiErr = err as ApiError
      setErrorMessage(apiErr.message ?? 'Invalid token or an unknown error occurred.')
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
          onClick={() => navigate('/request-reset')}
          aria-label="Back to request reset"
        >
          ← Back
        </button>

        <div className="auth-logo">
          <Logo size={80} />
        </div>

        <h1 className="auth-title">Enter Verification Token</h1>

        {usernameOrEmail && (
          <p style={{ color: 'rgba(255,255,255,0.8)', textAlign: 'center', lineHeight: 1.5, margin: 0 }}>
            Enter the verification token sent to {usernameOrEmail}.
          </p>
        )}

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

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <div className="auth-field">
            <label className="auth-label" htmlFor="verificationToken">
              Verification Token
            </label>
            <input
              id="verificationToken"
              className="auth-input"
              type="text"
              autoComplete="one-time-code"
              autoCapitalize="none"
              value={verificationToken}
              onChange={e => setVerificationToken(e.target.value)}
              disabled={isLoading}
            />
          </div>

          {isLoading ? (
            <div className="auth-spinner" aria-label="Verifying…">
              <span className="spinner" />
            </div>
          ) : (
            <button
              type="submit"
              className="auth-button"
              disabled={verificationToken.trim().length === 0}
            >
              Verify
            </button>
          )}
        </form>
      </div>
    </div>
  )
}

export default VerifyResetPage
