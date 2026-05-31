import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import Logo from '../components/Logo'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import './LoginPage.css'

function RequestResetPage() {
  const navigate = useNavigate()
  const [usernameOrEmail, setUsernameOrEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [didSucceed, setDidSucceed] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (usernameOrEmail.trim().length === 0) return
    setIsLoading(true)
    try {
      await apiClient.requestReset({ username_or_email: usernameOrEmail.trim() })
      setErrorMessage(null)
      setDidSucceed(true)
    } catch (err) {
      const apiErr = err as ApiError
      // Treat "account not found" the same as success to prevent user enumeration.
      if (apiErr.message === 'No user with that username or email') {
        setErrorMessage(null)
        setDidSucceed(true)
      } else {
        setErrorMessage(apiErr.message ?? 'Reset request failed. Please try again.')
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
          onClick={() => navigate('/login')}
          aria-label="Back to login"
        >
          ← Back
        </button>

        <div className="auth-logo">
          <Logo size={80} />
        </div>

        <h1 className="auth-title">Reset Password</h1>

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

        {didSucceed ? (
          <p style={{ color: 'rgba(255,255,255,0.8)', textAlign: 'center', lineHeight: 1.5 }}>
            If an account with that username or email exists, you&apos;ll receive reset
            instructions shortly.
          </p>
        ) : (
          <form className="auth-form" onSubmit={handleSubmit} noValidate>
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

            {isLoading ? (
              <div className="auth-spinner" aria-label="Submitting…">
                <span className="spinner" />
              </div>
            ) : (
              <button
                type="submit"
                className="auth-button"
                disabled={usernameOrEmail.trim().length === 0}
              >
                Request Reset
              </button>
            )}
          </form>
        )}
      </div>
    </div>
  )
}

export default RequestResetPage
