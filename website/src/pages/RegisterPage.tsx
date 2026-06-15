import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Logo from '../components/Logo'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import RequirementHints from '../auth/RequirementHints'
import { getPasswordRequirements, getUsernameRequirements, allMet } from '../auth/requirements'
import './LoginPage.css'

const PRIVACY_POLICY_TEXT =
  'We collect your username and password for authentication. We do not store your date of birth or any other personal information. We store your posts, comments, and related metadata such as like counts and reports. We also track follower/following relationships and blocked users to maintain the social environment.'

function RegisterPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [dateOfBirth, setDateOfBirth] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [showPrivacyPolicy, setShowPrivacyPolicy] = useState(false)

  useEffect(() => {
    if (!showPrivacyPolicy) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setShowPrivacyPolicy(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [showPrivacyPolicy])

  const usernameRequirements = getUsernameRequirements(username)
  const passwordRequirements = getPasswordRequirements(password)
  const isPasswordMatching = confirmPassword === '' || password === confirmPassword
  const isFormValid =
    allMet(usernameRequirements) &&
    email.trim().length > 0 &&
    dateOfBirth.length > 0 &&
    allMet(passwordRequirements) &&
    password === confirmPassword

  async function handleRegister() {
    if (!isFormValid) return
    setShowPrivacyPolicy(false)
    setIsLoading(true)
    try {
      const response = await apiClient.register({
        username: username.trim(),
        email: email.trim(),
        password,
        remember_me: false,
        date_of_birth: dateOfBirth,
      })
      localStorage.setItem('session_token', response.session_management_token)
      localStorage.setItem('user_id', response.user_id)
      localStorage.setItem('username', username.trim())
      navigate('/home')
    } catch (err) {
      const apiErr = err as ApiError
      setErrorMessage(apiErr.message ?? 'Registration failed. Username or email may be taken.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="auth-page">
      {showPrivacyPolicy && (
        <div className="modal-overlay">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="pp-title"
            aria-describedby="pp-body"
          >
            <h2 className="modal__title" id="pp-title">
              Privacy Policy
            </h2>
            <p className="modal__body" id="pp-body">{PRIVACY_POLICY_TEXT}</p>
            <div className="modal__actions">
              <button
                type="button"
                className="modal__cancel"
                onClick={() => setShowPrivacyPolicy(false)}
              >
                Cancel
              </button>
              <button type="button" className="modal__confirm" onClick={handleRegister} autoFocus>
                Ok
              </button>
            </div>
          </div>
        </div>
      )}

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

        <h1 className="auth-title">Create Account</h1>

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

        <form
          className="auth-form"
          onSubmit={e => {
            e.preventDefault()
            if (isFormValid) setShowPrivacyPolicy(true)
          }}
          noValidate
        >
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
            {username.length > 0 && (
              <RequirementHints requirements={usernameRequirements} label="Username requirements" />
            )}
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
            <label className="auth-label" htmlFor="dateOfBirth">
              Date of Birth
            </label>
            <input
              id="dateOfBirth"
              className="auth-input"
              type="date"
              value={dateOfBirth}
              onChange={e => setDateOfBirth(e.target.value)}
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
              autoComplete="new-password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              disabled={isLoading}
            />
            {password.length > 0 && (
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
            <div className="auth-spinner" aria-label="Registering…">
              <span className="spinner" />
            </div>
          ) : (
            <button type="submit" className="auth-button" disabled={!isFormValid}>
              Register
            </button>
          )}
        </form>
      </div>
    </div>
  )
}

export default RegisterPage

export { PRIVACY_POLICY_TEXT }
