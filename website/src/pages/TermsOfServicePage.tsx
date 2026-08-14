import { Link } from 'react-router'
import Logo from '../components/Logo'
import {
  TERMS_OF_SERVICE_LAST_UPDATED,
  TERMS_OF_SERVICE_SECTIONS,
} from '../termsOfService'
import './LegalPage.css'

/**
 * Unauthenticated terms of service page, reachable at /terms-of-service
 * without logging in (issue #493). Google's OAuth consent screen and the app
 * store listings all want a stable public terms URL, so this is it; the text
 * is the same one the in-app Settings modal shows.
 */
function TermsOfServicePage() {
  return (
    <div className="legal-page">
      <nav className="legal-page__nav">
        <Link to="/" className="legal-page__home-link">
          <Logo size={32} />
        </Link>
      </nav>

      <main className="legal-page__main">
        <h1 className="legal-page__title">Terms of Service</h1>
        <p className="legal-page__updated">
          Last updated {TERMS_OF_SERVICE_LAST_UPDATED}
        </p>

        {TERMS_OF_SERVICE_SECTIONS.map(section => (
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
          , and you can close your account from the{' '}
          <Link to="/delete-account" className="legal-page__link">
            account &amp; data deletion page
          </Link>.
        </p>
      </main>
    </div>
  )
}

export default TermsOfServicePage
