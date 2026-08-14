import { Link } from 'react-router'
import Logo from '../components/Logo'
import { PRIVACY_POLICY_TEXT } from '../privacyPolicy'
import './LegalPage.css'

/**
 * Unauthenticated privacy policy page, reachable at /privacy-policy without
 * logging in. Exists so app store listings (Apple/Google) have a stable
 * public URL to link to; mirrors the text shown in the in-app modals.
 */
function PrivacyPolicyPage() {
  return (
    <div className="legal-page">
      <nav className="legal-page__nav">
        <Link to="/" className="legal-page__home-link">
          <Logo size={32} />
        </Link>
      </nav>

      <main className="legal-page__main">
        <h1 className="legal-page__title">Privacy Policy</h1>
        <p className="legal-page__body">{PRIVACY_POLICY_TEXT}</p>
        <p className="legal-page__body legal-page__aside">
          Using Good Vibes Only is also subject to the{' '}
          <Link to="/terms-of-service" className="legal-page__link">
            Terms of Service
          </Link>. To permanently delete your account and all associated data,
          visit the{' '}
          <Link to="/delete-account" className="legal-page__link">
            account &amp; data deletion page
          </Link>.
        </p>
      </main>
    </div>
  )
}

export default PrivacyPolicyPage
