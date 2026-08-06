import { useCallback, useRef, useState, useEffect } from 'react'
import { useNavigate } from 'react-router'
import GoogleSignInButton from '../components/GoogleSignInButton'
import Logo from '../components/Logo'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import { clearSession, persistSession } from '../api/session'
import RequirementHints from '../auth/RequirementHints'
import { getPasswordRequirements, getUsernameRequirements, allMet } from '../auth/requirements'
import { MAX_FREEFORM_INTERESTS } from '../api/interestVocabulary'
import InterestPicker from '../components/InterestPicker'
import type { InterestOption } from '../api/types'
import { isTwoFactorRequired } from '../api/types'
import { PRIVACY_POLICY_TEXT } from '../privacyPolicy'
import { registerForPush } from '../push/webPush'
import './LoginPage.css'

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
  // The "You're member #n!" greeting shown after a successful signup (#198).
  // memberNumber is null in the rare case the backend couldn't assign one.
  const [showWelcome, setShowWelcome] = useState(false)
  const [memberNumber, setMemberNumber] = useState<number | null>(null)
  // Google sign-up (issue #10). The credential is held here between Google's
  // callback and the privacy-policy acknowledgement: consent is a condition of
  // creating an account, and Google's button can't be made to ask for it first.
  const [pendingGoogleToken, setPendingGoogleToken] = useState<string | null>(null)
  // A Google account arrives already signed in and already email-verified, so
  // its welcome modal says something different and leads somewhere else than
  // the password path's "go check your inbox".
  const [signedUpWithGoogle, setSignedUpWithGoogle] = useState(false)
  // Optional positive-interest picks collected during sign-up (issues #446/#35),
  // sent along in the register call since the account has no session yet.
  const [interestOptions, setInterestOptions] = useState<InterestOption[]>([])
  const [selectedInterests, setSelectedInterests] = useState<string[]>([])
  const [freeformInterests, setFreeformInterests] = useState<string[]>([])
  const continueButtonRef = useRef<HTMLButtonElement>(null)

  // Load the preset bucket vocabulary (public endpoint). Best-effort: if it
  // fails the picker simply shows no presets and freeform entry still works.
  useEffect(() => {
    let cancelled = false
    apiClient
      .getInterestOptions()
      .then(res => {
        if (!cancelled) setInterestOptions(res.options)
      })
      .catch(() => {
        // Non-fatal — interests are optional at sign-up.
      })
    return () => {
      cancelled = true
    }
  }, [])

  function toggleInterest(slug: string) {
    setSelectedInterests(prev =>
      prev.includes(slug) ? prev.filter(s => s !== slug) : [...prev, slug],
    )
  }

  function addFreeformInterests(terms: string[]) {
    setFreeformInterests(prev => {
      const seen = new Set(prev.map(t => t.toLowerCase()))
      const next = [...prev]
      for (const term of terms) {
        const key = term.toLowerCase()
        if (!seen.has(key) && next.length < MAX_FREEFORM_INTERESTS) {
          seen.add(key)
          next.push(term)
        }
      }
      return next
    })
  }

  function removeFreeformInterest(term: string) {
    setFreeformInterests(prev => prev.filter(t => t !== term))
  }

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
      const result = await apiClient.register({
        username: username.trim(),
        email: email.trim(),
        password,
        remember_me: false,
        date_of_birth: dateOfBirth,
        interest_categories: selectedInterests,
        interest_freeform: freeformInterests,
      })
      // Drop the registration session and any persisted session/remember-me
      // tokens right away: the account can't act until email verification, and
      // if the user reloads while the welcome modal is up, main.tsx must not
      // restore a stale session from a previous login. Do this before showing
      // the modal so there's no window where an old session could be restored.
      clearSession()
      // Greet the new member with their join number before sending them off to
      // verify their email (#198). Navigation happens when they dismiss it.
      setMemberNumber(result.membership_number ?? null)
      setShowWelcome(true)
    } catch (err) {
      const apiErr = err as ApiError
      setErrorMessage(apiErr.message ?? 'Registration failed. Username or email may be taken.')
    } finally {
      setIsLoading(false)
    }
  }

  /** Google's callback: hold the credential until the privacy policy is accepted. */
  function handleGoogleCredential(idToken: string) {
    if (isLoading) return
    setErrorMessage(null)
    setPendingGoogleToken(idToken)
    setShowPrivacyPolicy(true)
  }

  async function handleGoogleSignUp() {
    const idToken = pendingGoogleToken
    if (!idToken) return
    setShowPrivacyPolicy(false)
    setPendingGoogleToken(null)
    setIsLoading(true)
    try {
      const response = await apiClient.loginWithGoogle({ id_token: idToken })

      if (isTwoFactorRequired(response)) {
        // Only an *existing* account can owe a second factor, so this is
        // someone who already has one. The code-entry step lives on the login
        // page; duplicating it here would mean two copies of the 2FA flow, so
        // send them there instead.
        clearSession()
        setErrorMessage(
          'You already have an account with two-factor authentication. Please sign in from the Login page.',
        )
        return
      }

      // Unlike the password path this session is usable immediately: Google has
      // already verified the address, so there is no email to go and click.
      persistSession(response, false)
      void registerForPush({ promptIfNeeded: true })
      setMemberNumber(response.membership_number ?? null)
      setSignedUpWithGoogle(true)
      setShowWelcome(true)
    } catch (err) {
      const apiErr = err as ApiError
      setErrorMessage(apiErr.message ?? 'Google sign-up failed. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  // Dismissing the welcome modal just moves on to email verification; the
  // session was already cleared in handleRegister. The user logs in after
  // verifying. A Google sign-up has neither of those to do — it is already
  // signed in and already verified — so it goes straight into the app.
  const dismissWelcome = useCallback(() => {
    if (signedUpWithGoogle) {
      navigate('/home')
      return
    }
    navigate('/check-email', { state: { email: email.trim() } })
  }, [navigate, email, signedUpWithGoogle])

  // While the welcome modal is open, Escape dismisses it (matching the
  // privacy-policy modal) and Tab is trapped on the modal's only control so
  // keyboard/screen-reader users can't tab "behind" it into the page.
  useEffect(() => {
    if (!showWelcome) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        dismissWelcome()
      } else if (e.key === 'Tab') {
        // Single-control dialog: keep focus on Continue rather than letting it
        // escape to the still-mounted form/Back button underneath.
        e.preventDefault()
        continueButtonRef.current?.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [showWelcome, dismissWelcome])

  return (
    <div className="auth-page">
      {showWelcome && (
        <div className="modal-overlay">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="welcome-title"
            aria-describedby="welcome-body"
          >
            <h2 className="modal__title" id="welcome-title">
              Welcome to Good Vibes Only! 🎉
            </h2>
            <p className="modal__body" id="welcome-body">
              {signedUpWithGoogle
                ? memberNumber != null
                  ? `You're member #${memberNumber.toLocaleString()}! You're all set — start spreading good vibes.`
                  : `You're all set — start spreading good vibes.`
                : memberNumber != null
                  ? `You're member #${memberNumber.toLocaleString()}! Check your email to verify your account and start spreading good vibes.`
                  : `You're all set! Check your email to verify your account and start spreading good vibes.`}
            </p>
            <div className="modal__actions">
              <button
                ref={continueButtonRef}
                type="button"
                className="modal__confirm"
                onClick={dismissWelcome}
                autoFocus
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      )}

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
                onClick={() => {
                  setShowPrivacyPolicy(false)
                  // Declining consent discards the Google credential rather
                  // than leaving it primed for the next confirmation.
                  setPendingGoogleToken(null)
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="modal__confirm"
                onClick={pendingGoogleToken ? handleGoogleSignUp : handleRegister}
                autoFocus
              >
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
            if (!isFormValid) return
            // Whatever the modal is about to confirm, it is this form — drop any
            // Google credential still held from an abandoned attempt so the
            // shared "Ok" button can't run the wrong one.
            setPendingGoogleToken(null)
            setShowPrivacyPolicy(true)
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

          <div className="auth-field">
            <span className="auth-label">Interests (optional)</span>
            <InterestPicker
              options={interestOptions}
              selectedSlugs={selectedInterests}
              onToggleSlug={toggleInterest}
              freeformTerms={freeformInterests}
              onAddFreeform={addFreeformInterests}
              onRemoveFreeform={removeFreeformInterest}
              disabled={isLoading}
            />
          </div>

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

        {/* A Google sign-up skips every field above — Google supplies the
            email, the backend generates a username, and there is no password. */}
        <GoogleSignInButton
          onCredential={handleGoogleCredential}
          onError={setErrorMessage}
          disabled={isLoading}
          text="signup_with"
        />
      </div>
    </div>
  )
}

export default RegisterPage
