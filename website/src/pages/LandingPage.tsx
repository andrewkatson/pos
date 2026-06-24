import { useNavigate } from 'react-router-dom'
import Logo from '../components/Logo'
import './LandingPage.css'

function LandingPage() {
  const navigate = useNavigate()

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
    </div>
  )
}

export default LandingPage
