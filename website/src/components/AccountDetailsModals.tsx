import { useState } from 'react'
import { ACCOUNT_CHANGE_MESSAGES, apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import { updateStoredUsername } from '../api/session'
import { allMet, getUsernameRequirements } from '../auth/requirements'
import { isGoogleSignInConfigured } from '../auth/googleIdentity'
import GoogleSignInButton from './GoogleSignInButton'
import Modal from './Modal'

/** The copy for an error from the username/email change endpoints (issue #594):
 * stable codes map to our own wording, anything else is already readable. */
function accountChangeMessage(err: unknown, fallback: string): string {
  const message = (err as ApiError).message
  return ACCOUNT_CHANGE_MESSAGES[message] ?? message ?? fallback
}

interface ChangeUsernameModalProps {
  currentUsername: string
  onClose: () => void
  /** Called with the new name and when the next rename is allowed. */
  onChanged: (username: string, nextChangeTime: string | null) => void
}

/**
 * Rename the account from Settings (issue #594). The backend checks the name
 * like a registration one (pattern, availability, positivity) and allows one
 * rename per cooldown; the old name stays reserved for this account for a while,
 * so links to it keep working.
 */
export function ChangeUsernameModal({ currentUsername, onClose, onChanged }: ChangeUsernameModalProps) {
  const [username, setUsername] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isBusy, setIsBusy] = useState(false)

  const trimmed = username.trim()
  const requirements = getUsernameRequirements(trimmed)
  const isValid = allMet(requirements)
  const isDifferent = trimmed !== currentUsername
  const canSubmit = trimmed.length > 0 && isValid && isDifferent && !isBusy

  async function handleChange() {
    if (!canSubmit) return
    setIsBusy(true)
    setErrorMessage(null)
    try {
      const result = await apiClient.changeUsername({ username: trimmed })
      updateStoredUsername(result.username)
      onChanged(result.username, result.next_username_change_time)
    } catch (err) {
      setErrorMessage(accountChangeMessage(err, 'Could not change your username.'))
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <Modal title="Change Username">
      <p className="modal__body">
        You can change your username once every 30 days. Your old username stays reserved for
        you for 30 days, so links to your profile keep working.
      </p>

      {errorMessage && (
        <p className="twofa-error" role="alert">
          {errorMessage}
        </p>
      )}

      <input
        className="search-bar"
        type="text"
        autoComplete="username"
        autoCapitalize="none"
        aria-label="New username"
        placeholder="New username"
        value={username}
        onChange={e => setUsername(e.target.value)}
        disabled={isBusy}
      />

      <div aria-live="polite">
        {trimmed.length > 0 &&
          requirements
            .filter(r => !r.didMeetRequirement)
            .map(r => (
              <p key={r.label} className="modal__body">
                {r.label}
              </p>
            ))}
        {trimmed.length > 0 && !isDifferent && (
          <p className="modal__body">That's already your username.</p>
        )}
      </div>

      <div className="modal__actions">
        <button type="button" className="modal__cancel" onClick={onClose} disabled={isBusy}>
          Cancel
        </button>
        <button type="button" className="modal__confirm" disabled={!canSubmit} onClick={handleChange}>
          Change Username
        </button>
      </div>
    </Modal>
  )
}

interface ChangeEmailModalProps {
  currentEmail: string
  /** False for a Google-only account: it confirms with Google, not a password. */
  hasPassword: boolean
  onClose: () => void
  /** Called with the address now waiting on its confirmation link. */
  onRequested: (pendingEmail: string) => void
}

const EMAIL_PATTERN = /^[^@]+@[^@]+\.[^@]+$/

/**
 * Ask to move the account to a new email (issue #594). Nothing changes until the
 * link sent to the new address is followed. The password is asked for so a
 * stolen session alone can't redirect password resets; a Google-only account
 * has none and signs in with Google again instead.
 */
export function ChangeEmailModal({ currentEmail, hasPassword, onClose, onRequested }: ChangeEmailModalProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isBusy, setIsBusy] = useState(false)

  const trimmed = email.trim()
  const isValid = EMAIL_PATTERN.test(trimmed)
  const isDifferent = trimmed.toLowerCase() !== currentEmail.toLowerCase()
  const canSubmitEmail = isValid && isDifferent && !isBusy
  const canSubmit = canSubmitEmail && password.length > 0

  async function submit(proof: { password?: string; id_token?: string }) {
    setIsBusy(true)
    setErrorMessage(null)
    try {
      const result = await apiClient.requestEmailChange({ email: trimmed, ...proof })
      onRequested(result.pending_email)
    } catch (err) {
      setErrorMessage(accountChangeMessage(err, 'Could not change your email.'))
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <Modal title="Change Email">
      <p className="modal__body">
        We&apos;ll send a link to your new address. Your email changes once you open it — until
        then, your current address keeps working.
      </p>

      {errorMessage && (
        <p className="twofa-error" role="alert">
          {errorMessage}
        </p>
      )}

      <input
        className="search-bar"
        type="email"
        inputMode="email"
        autoComplete="email"
        autoCapitalize="none"
        aria-label="New email"
        placeholder="New email"
        value={email}
        onChange={e => setEmail(e.target.value)}
        disabled={isBusy}
      />
      {hasPassword && (
        <input
          className="search-bar"
          type="password"
          autoComplete="current-password"
          aria-label="Current password"
          placeholder="Current password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          disabled={isBusy}
        />
      )}

      <div aria-live="polite">
        {trimmed.length > 0 && !isValid && <p className="modal__body">Enter a valid email address.</p>}
        {isValid && !isDifferent && <p className="modal__body">That's already your email.</p>}
      </div>

      {!hasPassword && (
        <>
          <p className="modal__body">Sign in with Google again to confirm it&apos;s you.</p>
          {isGoogleSignInConfigured() ? (
            <GoogleSignInButton
              text="continue_with"
              disabled={!canSubmitEmail}
              onCredential={idToken => void submit({ id_token: idToken })}
              onError={message => setErrorMessage(message)}
              unavailableMessage="Google sign-in is unavailable right now. Please try again later."
            />
          ) : (
            <p className="modal__body">Google sign-in isn&apos;t available right now.</p>
          )}
        </>
      )}

      <div className="modal__actions">
        <button type="button" className="modal__cancel" onClick={onClose} disabled={isBusy}>
          Cancel
        </button>
        {hasPassword && (
          <button
            type="button"
            className="modal__confirm"
            disabled={!canSubmit}
            onClick={() => void submit({ password })}
          >
            Send Link
          </button>
        )}
      </div>
    </Modal>
  )
}
