import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Logo from '../components/Logo'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import './LoginPage.css'

// Shown right after registration: the account exists but cannot log in until
// the verification link in the welcome email is clicked.
function CheckEmailPage() {
  const navigate = useNavigate()
  const location = useLocation()
  // Navigation state is lost on refresh or when the page is opened directly,
  // so it is only a convenience — without it the page asks who to resend to
  // instead of turning the user away (their account already exists).
  const email = (location.state as { email?: string } | null)?.email ?? ''

  const [usernameOrEmail, setUsernameOrEmail] = useState(email)
  const [isResending, setIsResending] = useState(false)
  const [resendMessage, setResendMessage] = useState<string | null>(null)

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

        <h1 className="auth-title">Check Your Email</h1>

        <p style={{ color: 'rgba(255,255,255,0.8)', textAlign: 'center', lineHeight: 1.5, margin: 0 }}>
          {email
            ? `We sent a verification link to ${email}. Click it to activate your account — you won't be able to log in until your email is verified.`
            : "We sent a verification link to the email address you registered with. Click it to activate your account — you won't be able to log in until your email is verified."}
        </p>

        <form className="auth-form" onSubmit={handleResend} noValidate>
          {!email && (
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
          )}

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

        <button
          type="button"
          className="auth-link auth-link--right"
          onClick={() => navigate('/login')}
        >
          Go to Login
        </button>
      </div>
    </div>
  )
}

export default CheckEmailPage
