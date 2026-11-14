import { Link } from 'react-router'
import Logo from '../components/Logo'
import { SUPPORT_EMAIL, SUPPORT_SECTIONS } from '../support'
import './LegalPage.css'

/**
 * Unauthenticated support page, reachable at /support without logging in.
 *
 * Apple requires a Support URL on every App Store listing, and it has to be
 * useful to someone who cannot sign in — a suspended user, or a shopper who
 * has not installed the app yet. Shares the legal-page shell with the privacy
 * policy and the terms so the three can't drift apart visually.
 */
function SupportPage() {
  return (
    <div className="legal-page">
      <nav className="legal-page__nav">
        <Link to="/" className="legal-page__home-link">
          <Logo size={32} />
        </Link>
      </nav>

      <main className="legal-page__main">
        <h1 className="legal-page__title">Support</h1>
        <p className="legal-page__body">
          Questions, bug reports, moderation disputes, and anything else about
          Good Vibes Only all go to one address, and a person reads them.
        </p>
        <p className="legal-page__email">
          <a href={`mailto:${SUPPORT_EMAIL}`} className="legal-page__link">
            {SUPPORT_EMAIL}
          </a>
        </p>

        {SUPPORT_SECTIONS.map(section => (
          <section key={section.heading} className="legal-page__section">
            <h2 className="legal-page__section-heading">{section.heading}</h2>
            <p className="legal-page__body">{section.body}</p>
          </section>
        ))}

        <p className="legal-page__body legal-page__aside">
          What we collect and why is set out in the{' '}
          <Link to="/privacy-policy" className="legal-page__link">
            Privacy Policy
          </Link>
          , the rules of the place are in the{' '}
          <Link to="/terms-of-service" className="legal-page__link">
            Terms of Service
          </Link>
          , and you can close your account from the{' '}
          <Link to="/delete-account" className="legal-page__link">
            account &amp; data deletion page
          </Link>.
        </p>
      </main>
    </div>
  )
}

export default SupportPage
