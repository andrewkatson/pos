import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate, useLocation } from 'react-router-dom'
import Logo from '../components/Logo'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import { isTwoFactorRequired } from '../api/types'
import RequirementHints from '../auth/RequirementHints'
import { getPasswordRequirements, allMet } from '../auth/requirements'
import './LoginPage.css'

function ResetPasswordPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const state = location.state as { usernameOrEmail?: string; resetToken?: string } | null
  const usernameOrEmail = state?.usernameOrEmail ?? ''
  const resetToken = state?.resetToken ?? ''

  const [username, setUsername] = useState(
    usernameOrEmail && !usernameOrEmail.includes('@') ? usernameOrEmail : '',
  )
  const [email, setEmail] = useState(
    usernameOrEmail.includes('@') ? usernameOrEmail : '',
  )
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  if (!resetToken) {
    return <Navigate to="/request-reset" replace />
  }

  const passwordRequirements = getPasswordRequirements(newPassword)
  const isPasswordMatching = confirmPassword === '' || newPassword === confirmPassword
  const isFormValid =
    username.trim().length > 0 &&
    email.trim().length > 0 &&
    allMet(passwordRequirements) &&
    newPassword === confirmPassword

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!isFormValid) return
    setIsLoading(true)
    try {
      await apiClient.resetPassword({
        username: username.trim(),
        email: email.trim(),
        password: newPassword,
        reset_token: resetToken.trim(),
      })
      const response = await apiClient.login({
        username_or_email: username.trim() || email.trim(),
        password: newPassword,
      })
      // If the account has two-factor enabled, login returns a challenge, not
      // a session — send the user to the login page to finish signing in with
      // their authenticator rather than auto-entering the app.
      if (isTwoFactorRequired(response)) {
        navigate('/login')
        return
      }
      localStorage.setItem('session_token', response.session_management_token)
      localStorage.setItem('user_id', response.user_id)
      if (response.username) {
        localStorage.setItem('username', response.username)
      }
      navigate('/home')
    } catch (err) {
      const apiErr = err as ApiError
      setErrorMessage(apiErr.message ?? 'Password reset failed. Please try again.')
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
          onClick={() => navigate('/verify-reset', { state: { usernameOrEmail } })}
          aria-label="Back to verify reset"
        >
          ← Back
        </button>

        <div className="auth-logo">
          <Logo size={80} />
        </div>

        <h1 className="auth-title">Set New Password</h1>

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
            <label className="auth-label" htmlFor="username">
              Username
            </label>
            <input
              id="username"
              className="auth-input"
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              value={username}
              onChange={e => setUsername(e.target.value)}
              disabled={isLoading}
            />
          </div>

          <div className="auth-field">
            <label className="auth-label" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              className="auth-input"
              type="email"
              autoComplete="email"
              autoCapitalize="none"
              value={email}
              onChange={e => setEmail(e.target.value)}
              disabled={isLoading}
            />
          </div>

          <div className="auth-field">
            <label className="auth-label" htmlFor="newPassword">
              New Password
            </label>
            <input
              id="newPassword"
              className="auth-input"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              disabled={isLoading}
            />
            {newPassword.length > 0 && (
              <RequirementHints requirements={passwordRequirements} label="Password requirements" />
            )}
          </div>

          <div className="auth-field">
            <label className="auth-label" htmlFor="confirmPassword">
              Confirm Password
            </label>
            <input
              id="confirmPassword"
              className="auth-input"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              disabled={isLoading}
            />
          </div>

          {!isPasswordMatching && (
            <p className="auth-mismatch" role="alert">
              Passwords do not match.
            </p>
          )}

          {isLoading ? (
            <div className="auth-spinner" aria-label="Resetting password…">
              <span className="spinner" />
            </div>
          ) : (
            <button
              type="submit"
              className="auth-button"
              disabled={!isFormValid}
            >
              Reset Password and Login
            </button>
          )}
        </form>
      </div>
    </div>
  )
}

export default ResetPasswordPage
