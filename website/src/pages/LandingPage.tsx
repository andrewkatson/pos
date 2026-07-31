import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router'
import { apiClient } from '../api/client'
import Logo from '../components/Logo'
import './LandingPage.css'

function LandingPage() {
  const navigate = useNavigate()

  // A remembered session is restored into the ApiClient on startup (see
  // main.tsx). If we're already signed in, skip this logged-out marketing
  // screen and go straight into the app — otherwise a returning "Remember Me"
  // user is shown the landing page and has to sign in (and clear 2FA) again,
  // making it look like the session was dropped (issue #411).
  useEffect(() => {
    if (apiClient.isAuthenticated()) {
      navigate('/home', { replace: true })
    }
  }, [navigate])

  return (
    <div className="landing">
      <nav className="landing__nav">
        <button
          type="button"
          className="landing__nav-button landing__nav-button--login"
          onClick={() => navigate('/login')}
        >
          Login
        </button>
        <button
          type="button"
          className="landing__nav-button landing__nav-button--signup"
          onClick={() => navigate('/register')}
        >
          Sign up
        </button>
      </nav>

      <main className="landing__main">
        <div className="landing__card">
          <Logo size={120} />
          <h1 className="landing__title">Good Vibes Only</h1>
          <p className="landing__subtitle">A positive-only social network.</p>
        </div>
      </main>

      <footer className="landing__footer">
        <Link to="/privacy-policy" className="landing__footer-link">
          Privacy Policy
        </Link>
        <Link to="/delete-account" className="landing__footer-link">
          Delete Account
        </Link>
      </footer>
    </div>
  )
}

export default LandingPage
