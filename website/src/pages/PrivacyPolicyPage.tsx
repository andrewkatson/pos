import { Link } from 'react-router-dom'
import Logo from '../components/Logo'
import { PRIVACY_POLICY_TEXT } from '../privacyPolicy'
import './PrivacyPolicyPage.css'

/**
 * Unauthenticated privacy policy page, reachable at /privacy-policy without
 * logging in. Exists so app store listings (Apple/Google) have a stable
 * public URL to link to; mirrors the text shown in the in-app modals.
 */
function PrivacyPolicyPage() {
  return (
    <div className="privacy-page">
      <nav className="privacy-page__nav">
        <Link to="/" className="privacy-page__home-link">
          <Logo size={32} />
        </Link>
      </nav>

      <main className="privacy-page__main">
        <h1 className="privacy-page__title">Privacy Policy</h1>
        <p className="privacy-page__body">{PRIVACY_POLICY_TEXT}</p>
      </main>
    </div>
  )
}

export default PrivacyPolicyPage
