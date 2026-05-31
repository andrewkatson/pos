import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import Logo from '../components/Logo'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import './LoginPage.css'

const PRIVACY_POLICY_TEXT =
  'We collect your username and password for authentication. We do not store your date of birth or any other personal information. We store your posts, comments, and related metadata such as like counts and reports. We also track follower/following relationships and blocked users to maintain the social environment.'

function LoginPage() {
  const navigate = useNavigate()
  const [usernameOrEmail, setUsernameOrEmail] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

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
      localStorage.setItem('session_token', response.session_management_token)
      localStorage.setItem('user_id', response.user_id)
      if (response.username) {
        localStorage.setItem('username', response.username)
      }
      navigate('/')
    } catch (err) {
      const apiErr = err as ApiError
      setErrorMessage(apiErr.message ?? 'Login failed. Please check your credentials.')
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

// Keep the privacy policy text accessible for tests / storybook.
export { PRIVACY_POLICY_TEXT }
