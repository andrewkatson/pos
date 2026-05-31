import Logo from '../components/Logo'
import './LandingPage.css'

/**
 * Public landing page: a plain black background with a large "Good Vibes Only"
 * title card and the smiley logo, plus Login / Sign up buttons in the top-right.
 * The auth buttons are intentionally inert for now.
 */
function LandingPage() {
  return (
    <div className="landing">
      <nav className="landing__nav">
        <button type="button" className="landing__nav-button landing__nav-button--login">
          Login
        </button>
        <button type="button" className="landing__nav-button landing__nav-button--signup">
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
