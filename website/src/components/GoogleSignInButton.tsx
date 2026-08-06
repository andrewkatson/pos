import { useEffect, useRef, useState } from 'react'
import {
  googleClientId,
  isGoogleSignInConfigured,
  loadGoogleIdentityServices,
} from '../auth/googleIdentity'

interface GoogleSignInButtonProps {
  /** Called with the Google ID token once the user picks an account. */
  onCredential: (idToken: string) => void
  /** Called when Google itself could not be reached or set up. */
  onError?: (message: string) => void
  /** Google's button is an iframe we cannot disable, so it is hidden instead. */
  disabled?: boolean
  /** 'signin_with' on the login page, 'signup_with' on the register page. */
  text?: 'signin_with' | 'signup_with' | 'continue_with'
}

/**
 * Google's own rendered sign-in button (issue #10).
 *
 * The button has to be drawn by Google — their branding terms require their
 * markup, and the credential callback only fires for a button GIS rendered
 * itself — so this component owns a bare container and hands it over. Renders
 * nothing when no client ID is configured.
 */
function GoogleSignInButton({
  onCredential,
  onError,
  disabled = false,
  text = 'signin_with',
}: GoogleSignInButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isReady, setIsReady] = useState(false)

  // Held in refs so the setup effect below never re-runs (and re-renders
  // Google's button) just because the page re-rendered with a new callback
  // identity. Kept current in an effect rather than during render, and always
  // long before either can fire — both are only reached from a user action.
  const onCredentialRef = useRef(onCredential)
  const onErrorRef = useRef(onError)
  useEffect(() => {
    onCredentialRef.current = onCredential
    onErrorRef.current = onError
  })

  useEffect(() => {
    if (!isGoogleSignInConfigured()) return

    let cancelled = false

    loadGoogleIdentityServices()
      .then(google => {
        if (cancelled || !containerRef.current) return
        google.id.initialize({
          client_id: googleClientId(),
          callback: response => onCredentialRef.current(response.credential),
          // Never sign someone in without them asking: a returning visitor
          // should land on the login page, not be silently authenticated by a
          // Google session they forgot they had.
          auto_select: false,
        })
        google.id.renderButton(containerRef.current, {
          type: 'standard',
          theme: 'filled_black',
          size: 'large',
          shape: 'pill',
          text,
          logo_alignment: 'center',
        })
        setIsReady(true)
      })
      .catch(() => {
        if (cancelled) return
        onErrorRef.current?.('Google sign-in is unavailable right now. Please use your password.')
      })

    return () => {
      cancelled = true
    }
  }, [text])

  if (!isGoogleSignInConfigured()) {
    return null
  }

  return (
    <div className="auth-google">
      {isReady && (
        <div className="auth-divider">
          <span>or</span>
        </div>
      )}
      <div
        ref={containerRef}
        className="auth-google__button"
        // Google renders an iframe we cannot put a `disabled` attribute on, so
        // it is hidden outright while a request is in flight — a click that
        // arrived mid-login would start a second one.
        hidden={disabled}
        data-testid="google-sign-in-button"
      />
    </div>
  )
}

export default GoogleSignInButton
