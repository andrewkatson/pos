import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import Logo from '../components/Logo'
import { ACCOUNT_CHANGE_MESSAGES, apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import './LoginPage.css'

type ConfirmState = 'missing-token' | 'confirming' | 'success' | 'error'

interface ConfirmResult {
  token: string
  state: 'success' | 'error'
  message?: string
}

const BODY_STYLE = { color: 'rgba(255,255,255,0.8)', textAlign: 'center', lineHeight: 1.5, margin: 0 } as const

// Landing page for the link sent to a new email address
// (https://smiling.social/verify-email-change?token=..., issue #594). Confirms
// automatically on load. Needs no session: the link may be opened anywhere.
function VerifyEmailChangePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [result, setResult] = useState<ConfirmResult | null>(null)

  // Single-use token: guard against the effect running twice for the same
  // token (StrictMode) and reporting a false failure, as VerifyEmailPage does.
  const requestedToken = useRef<string | null>(null)

  useEffect(() => {
    if (!token || requestedToken.current === token) return
    requestedToken.current = token
    const isCurrent = () => requestedToken.current === token
    apiClient
      .confirmEmailChange({ verification_token: token })
      .then(() => {
        if (isCurrent()) setResult({ token, state: 'success' })
      })
      .catch((err: ApiError) => {
        if (isCurrent()) {
          setResult({
            token,
            state: 'error',
            message:
              ACCOUNT_CHANGE_MESSAGES[err.message] ??
              err.message ??
              'We could not confirm your new email. The link may have expired.',
          })
        }
      })
  }, [token])

  const state: ConfirmState = !token
    ? 'missing-token'
    : result?.token === token
      ? result.state
      : 'confirming'

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <Logo size={80} />
        </div>

        <h1 className="auth-title">Confirm New Email</h1>

        {state === 'confirming' && (
          <div className="auth-spinner" aria-label="Confirming…">
            <span className="spinner" />
          </div>
        )}

        {state === 'success' && (
          <p style={BODY_STYLE}>Your email address has been changed. Use it from now on to sign in.</p>
        )}

        {state === 'missing-token' && (
          <p style={BODY_STYLE}>
            This page confirms a new email address, but the link is missing its token. Please open
            the link from the email we sent to your new address.
          </p>
        )}

        {state === 'error' && (
          <>
            <div className="auth-error" role="alert">
              <p>{result?.message}</p>
            </div>
            <p style={BODY_STYLE}>
              Check Settings to see which email your account uses now — the change may already have
              gone through. If it hasn&apos;t, you can ask for a new link there.
            </p>
          </>
        )}

        <button type="button" className="auth-button" onClick={() => navigate('/')}>
          Continue
        </button>
      </div>
    </div>
  )
}

export default VerifyEmailChangePage
