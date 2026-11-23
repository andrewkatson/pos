import { useEffect, useState, useSyncExternalStore, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { apiClient } from '../api/client'
import { clearSession, getStoredSessionToken } from '../api/session'
import {
  beginPrivacyPolicyCheck,
  finishPrivacyPolicyCheck,
  getPrivacyPolicyStatus,
  markPrivacyPolicyAccepted,
  subscribeToPrivacyPolicyAcceptance,
} from '../auth/privacyPolicyConsent'
import { POLICY_VERSION, PRIVACY_POLICY_TEXT } from '../privacyPolicy'
import { isPublicPath } from '../publicPaths'
import Modal from './Modal'

/**
 * Routes reached while signed out, or while signing in or out. The gate never
 * shows on these: a stale session in storage must not put a consent dialog over
 * the login form, and someone deleting their account shouldn't have to agree to
 * anything first. Every other route is part of the signed-in app and is gated,
 * so a new authenticated page is covered without being listed here.
 */
const SIGNED_OUT_FLOW_PATHS = [
  '/',
  '/login',
  '/register',
  '/check-email',
  '/verify-email',
  '/request-reset',
  '/verify-reset',
  '/reset-password',
  '/delete-account',
]

function isSignedOutFlowPath(pathname: string): boolean {
  const normalized = pathname.toLowerCase().replace(/\/+$/, '') || '/'
  return SIGNED_OUT_FLOW_PATHS.includes(normalized) || isPublicPath(pathname)
}

/**
 * Asks a signed-in user to accept the privacy policy again before using the app
 * (issue #620), unless the backend already records an acceptance of this
 * build's POLICY_VERSION (or a newer one). It wraps the routes so it covers
 * every authenticated page. The dialog can't be dismissed: the only ways out
 * are accepting it, which the backend records, or logging out.
 *
 * While it is open — and while the check is still in flight — the wrapped page
 * is `inert`, so neither the mouse nor Tab can reach the app behind it; the
 * dialog's own controls are the only ones left to focus. The wrapper is
 * `display: contents` so it adds no layout box.
 */
function PrivacyPolicyReacceptGate({ children }: { children: ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const status = useSyncExternalStore(subscribeToPrivacyPolicyAcceptance, getPrivacyPolicyStatus)
  const [isLoggingOut, setIsLoggingOut] = useState(false)

  // Read on every render rather than cached: login and logout change storage and
  // then navigate, and the navigation is what re-renders this component.
  const signedIn = getStoredSessionToken() !== null
  const gated = signedIn && !isSignedOutFlowPath(location.pathname)
  const open = gated && status === 'needed'

  // Ask the backend which version this member last accepted, once per session.
  // A failed request leaves nothing known, so it asks.
  useEffect(() => {
    if (!gated || status !== 'unknown') return
    const check = beginPrivacyPolicyCheck()
    if (check === null) return
    apiClient.getCurrentUser().then(
      user => finishPrivacyPolicyCheck(check, user.policies_accepted_version ?? null),
      () => finishPrivacyPolicyCheck(check, undefined),
    )
  }, [gated, status])

  function handleAccept() {
    markPrivacyPolicyAccepted()
    // Best-effort, like logout: if it doesn't reach the backend the user is
    // simply asked again next time, which is no worse than not recording it.
    apiClient.acceptPolicies({ policy_version: POLICY_VERSION }).catch(() => {})
  }

  async function handleLogOut() {
    setIsLoggingOut(true)
    try {
      await apiClient.logout()
    } catch {
      // Log out locally even if the backend call fails (same as Settings).
    }
    clearSession()
    setIsLoggingOut(false)
    navigate('/')
  }

  return (
    <>
      <div className="privacy-reaccept__page" inert={gated && status !== 'accepted'}>
        {children}
      </div>
      {open && (
        <Modal
          title="Privacy Policy Updated"
          body="Please review our Privacy Policy. You need to accept it to keep using Good Vibes Only."
        >
          {/* Scrolls on its own so a short screen or enlarged text can't push
              the two buttons out of reach. Focusable so it scrolls by keyboard. */}
          <div
            className="privacy-reaccept__policy"
            role="region"
            aria-label="Privacy Policy"
            tabIndex={0}
          >
            <p className="modal__body">{PRIVACY_POLICY_TEXT}</p>
          </div>
          <div className="modal__actions">
            <button
              type="button"
              className="modal__cancel"
              onClick={handleLogOut}
              disabled={isLoggingOut}
            >
              Log Out
            </button>
            <button
              type="button"
              className="modal__confirm"
              onClick={handleAccept}
              disabled={isLoggingOut}
              autoFocus
            >
              Accept
            </button>
          </div>
        </Modal>
      )}
    </>
  )
}

export default PrivacyPolicyReacceptGate
