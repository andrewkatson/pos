import { useState, useSyncExternalStore } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { apiClient } from '../api/client'
import { clearSession, getStoredSessionToken } from '../api/session'
import {
  hasAcceptedPrivacyPolicy,
  markPrivacyPolicyAccepted,
  subscribeToPrivacyPolicyAcceptance,
} from '../auth/privacyPolicyConsent'
import { PRIVACY_POLICY_TEXT } from '../privacyPolicy'
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
 * (issue #620). Rendered once beside the routes so it covers every authenticated
 * page. The dialog can't be dismissed: the only ways out are accepting it or
 * logging out.
 */
function PrivacyPolicyReacceptGate() {
  const location = useLocation()
  const navigate = useNavigate()
  const accepted = useSyncExternalStore(
    subscribeToPrivacyPolicyAcceptance,
    hasAcceptedPrivacyPolicy,
  )
  const [isLoggingOut, setIsLoggingOut] = useState(false)

  // Read on every render rather than cached: login and logout change storage and
  // then navigate, and the navigation is what re-renders this component.
  const signedIn = getStoredSessionToken() !== null
  if (accepted || !signedIn || isSignedOutFlowPath(location.pathname)) {
    return null
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
    <Modal
      title="Privacy Policy Updated"
      body="Please review our Privacy Policy. You need to accept it to keep using Good Vibes Only."
    >
      <p className="modal__body">{PRIVACY_POLICY_TEXT}</p>
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
          onClick={markPrivacyPolicyAccepted}
          disabled={isLoggingOut}
          autoFocus
        >
          Accept
        </button>
      </div>
    </Modal>
  )
}

export default PrivacyPolicyReacceptGate
