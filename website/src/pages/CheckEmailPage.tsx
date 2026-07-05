import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import Logo from '../components/Logo'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import './LoginPage.css'

// Shown right after registration: the account exists but cannot log in until
// the verification link in the welcome email is clicked.
function CheckEmailPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const email = (location.state as { email?: string } | null)?.email ?? ''

  const [isResending, setIsResending] = useState(false)
  const [resendMessage, setResendMessage] = useState<string | null>(null)

  if (!email) {
    return <Navigate to="/register" replace />
  }

  async function handleResend() {
    setIsResending(true)
    setResendMessage(null)
    try {
      await apiClient.resendVerificationEmail({ username_or_email: email })
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
          We sent a verification link to {email}. Click it to activate your account — you
          won&apos;t be able to log in until your email is verified.
        </p>

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
          <button type="button" className="auth-button" onClick={handleResend}>
            Resend Verification Email
          </button>
        )}

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
