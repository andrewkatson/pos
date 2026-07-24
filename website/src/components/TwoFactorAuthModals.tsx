import { useEffect, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import Modal from './Modal'

/**
 * The two-factor authentication modals used by the Settings tab.
 *
 * Enrollment is the backend's two-step handshake (backend/user_system/views.py):
 * setup fetches a fresh secret + otpauth:// URI (rendered as a QR code and a
 * copyable secret), confirm proves one code from the authenticator works, and
 * the response's single-use recovery codes are shown exactly once.
 */

async function copyToClipboard(text: string): Promise<boolean> {
  // The Clipboard API is unavailable in insecure contexts / older browsers;
  // report failure rather than falsely showing "Copied".
  if (!navigator.clipboard) return false
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

interface EnableTwoFactorModalProps {
  onClose: () => void
  /** Called after 2FA is confirmed and the user has dismissed the recovery codes. */
  onEnabled: () => void
}

type EnrollStep = 'loading' | 'scan' | 'confirm' | 'codes'

export function EnableTwoFactorModal({ onClose, onEnabled }: EnableTwoFactorModalProps) {
  const [step, setStep] = useState<EnrollStep>('loading')
  const [secret, setSecret] = useState('')
  const [otpauthUri, setOtpauthUri] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([])
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  // Separate copy state per button so copying the secret on the scan step
  // doesn't leave the recovery-codes "Copy all" button reading "Copied".
  const [secretCopied, setSecretCopied] = useState(false)
  const [codesCopied, setCodesCopied] = useState(false)
  const [isBusy, setIsBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    apiClient
      .setupTotp()
      .then(response => {
        if (cancelled) return
        setSecret(response.totp_secret)
        setOtpauthUri(response.otpauth_uri)
        setStep('scan')
      })
      .catch((err: ApiError) => {
        if (cancelled) return
        setErrorMessage(err.message ?? 'Could not start two-factor setup.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const isCodeValid = /^\d{6}$/.test(code.trim())
  const canConfirm = isCodeValid && password.length > 0

  async function handleConfirm() {
    if (!canConfirm || isBusy) return
    setIsBusy(true)
    setErrorMessage(null)
    try {
      const response = await apiClient.confirmTotp({ password, totp_code: code.trim() })
      setRecoveryCodes(response.recovery_codes)
      setStep('codes')
    } catch (err) {
      setErrorMessage((err as ApiError).message ?? 'Verification failed. Please try again.')
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <Modal title="Enable Two-Factor Authentication">
      {errorMessage && (
        <p className="twofa-error" role="alert">
          {errorMessage}
        </p>
      )}

      {step === 'loading' && !errorMessage && <p className="modal__body">Loading…</p>}

      {step === 'loading' && errorMessage && (
        // Setup failed before a secret arrived: there's nothing to act on, so
        // give the user a way out of the modal.
        <div className="modal__actions">
          <button type="button" className="modal__confirm" onClick={onClose}>
            Close
          </button>
        </div>
      )}

      {step === 'scan' && (
        <>
          <p className="modal__body">
            Scan this QR code with your authenticator app (Google Authenticator, 1Password, …),
            or enter the secret manually.
          </p>
          <div className="twofa-qr">
            <QRCodeSVG value={otpauthUri} size={180} marginSize={2} />
          </div>
          <div className="twofa-secret-row">
            <code className="twofa-secret" aria-label="TOTP secret">
              {secret}
            </code>
            <button
              type="button"
              className="modal__cancel"
              onClick={async () => setSecretCopied(await copyToClipboard(secret))}
            >
              {secretCopied ? 'Copied' : 'Copy'}
            </button>
          </div>
          <div className="modal__actions">
            <button type="button" className="modal__cancel" onClick={onClose}>
              Cancel
            </button>
            <button type="button" className="modal__confirm" onClick={() => setStep('confirm')}>
              Next
            </button>
          </div>
        </>
      )}

      {step === 'confirm' && (
        <>
          <p className="modal__body">
            Enter the 6-digit code your authenticator app shows now, and your account password.
            The password is required so that someone who gets hold of your session cannot turn on
            two-factor authentication with their own app and lock you out.
          </p>
          <input
            className="search-bar"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            aria-label="Authenticator code"
            value={code}
            onChange={e => setCode(e.target.value)}
            disabled={isBusy}
          />
          <input
            className="search-bar"
            type="password"
            autoComplete="current-password"
            aria-label="Account password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            disabled={isBusy}
          />
          <div className="modal__actions">
            <button type="button" className="modal__cancel" onClick={onClose} disabled={isBusy}>
              Cancel
            </button>
            <button
              type="button"
              className="modal__confirm"
              disabled={!canConfirm || isBusy}
              onClick={handleConfirm}
            >
              Verify
            </button>
          </div>
        </>
      )}

      {step === 'codes' && (
        <>
          <p className="modal__body">
            Two-factor authentication is on. Save these recovery codes somewhere safe — each works
            once, and they are the only way back into your account if you lose your authenticator.
            They will not be shown again.
          </p>
          <ul className="twofa-codes" aria-label="Recovery codes">
            {recoveryCodes.map(recoveryCode => (
              <li key={recoveryCode}>
                <code>{recoveryCode}</code>
              </li>
            ))}
          </ul>
          <div className="modal__actions">
            <button
              type="button"
              className="modal__cancel"
              onClick={async () => setCodesCopied(await copyToClipboard(recoveryCodes.join('\n')))}
            >
              {codesCopied ? 'Copied' : 'Copy all'}
            </button>
            <button type="button" className="modal__confirm" onClick={onEnabled}>
              Done
            </button>
          </div>
        </>
      )}
    </Modal>
  )
}

interface DisableTwoFactorModalProps {
  onClose: () => void
  /** Called once 2FA has been turned off. */
  onDisabled: () => void
}

export function DisableTwoFactorModal({ onClose, onDisabled }: DisableTwoFactorModalProps) {
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [useRecoveryCode, setUseRecoveryCode] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isBusy, setIsBusy] = useState(false)

  const isCodeValid = useRecoveryCode
    ? /^[0-9a-fA-F]{10}$/.test(code.trim())
    : /^\d{6}$/.test(code.trim())
  const canSubmit = password.length > 0 && isCodeValid && !isBusy

  async function handleDisable() {
    if (!canSubmit) return
    setIsBusy(true)
    setErrorMessage(null)
    try {
      const trimmed = code.trim()
      await apiClient.disableTotp(
        useRecoveryCode
          ? { password, recovery_code: trimmed.toLowerCase() }
          : { password, totp_code: trimmed },
      )
      onDisabled()
    } catch (err) {
      setErrorMessage((err as ApiError).message ?? 'Could not disable two-factor authentication.')
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <Modal title="Disable Two-Factor Authentication">
      <p className="modal__body">
        Confirm your password and a current {useRecoveryCode ? 'recovery' : 'authenticator'} code
        to turn two-factor authentication off.
      </p>

      {errorMessage && (
        <p className="twofa-error" role="alert">
          {errorMessage}
        </p>
      )}

      <input
        className="search-bar"
        type="password"
        autoComplete="current-password"
        aria-label="Password"
        placeholder="Password"
        value={password}
        onChange={e => setPassword(e.target.value)}
        disabled={isBusy}
      />
      <input
        className="search-bar"
        type="text"
        inputMode={useRecoveryCode ? 'text' : 'numeric'}
        autoComplete="one-time-code"
        autoCapitalize="none"
        maxLength={useRecoveryCode ? 10 : 6}
        aria-label={useRecoveryCode ? 'Recovery code' : 'Authenticator code'}
        placeholder={useRecoveryCode ? 'Recovery code' : 'Authenticator code'}
        value={code}
        onChange={e => setCode(e.target.value)}
        disabled={isBusy}
      />
      <button
        type="button"
        className="twofa-toggle-kind"
        disabled={isBusy}
        onClick={() => {
          setUseRecoveryCode(v => !v)
          setCode('')
        }}
      >
        {useRecoveryCode ? 'Use an authenticator code instead' : 'Use a recovery code instead'}
      </button>

      <div className="modal__actions">
        <button type="button" className="modal__cancel" onClick={onClose} disabled={isBusy}>
          Cancel
        </button>
        <button
          type="button"
          className="modal__confirm"
          disabled={!canSubmit}
          onClick={handleDisable}
        >
          Disable
        </button>
      </div>
    </Modal>
  )
}

interface ChangePasswordModalProps {
  onClose: () => void
  /** Called once the password has been changed. */
  onChanged: () => void
}

// The full strength policy the backend enforces at registration (see
// Patterns.password in backend/user_system/constants.py): at least eight
// non-whitespace characters with a lower- and upper-case letter and a digit.
const STRONG_PASSWORD = /^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=\S+$).{8,}$/

/**
 * Change the signed-in account's password from Settings (issue #197). The
 * current password is required as well as the session, mirroring the backend,
 * so a stolen session alone cannot change it.
 */
export function ChangePasswordModal({ onClose, onChanged }: ChangePasswordModalProps) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isBusy, setIsBusy] = useState(false)

  const isNewStrong = STRONG_PASSWORD.test(newPassword)
  const doPasswordsMatch = newPassword === confirmPassword
  const isNewDifferent = newPassword !== currentPassword
  const canSubmit =
    currentPassword.length > 0 && isNewStrong && doPasswordsMatch && isNewDifferent && !isBusy

  async function handleChange() {
    if (!canSubmit) return
    setIsBusy(true)
    setErrorMessage(null)
    try {
      await apiClient.changePassword({ password: currentPassword, new_password: newPassword })
      onChanged()
    } catch (err) {
      setErrorMessage((err as ApiError).message ?? 'Could not change your password.')
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <Modal title="Change Password">
      <p className="modal__body">
        Enter your current password and choose a new one. Your new password must be at least 8
        characters and include an uppercase letter, a lowercase letter, and a number.
      </p>

      {errorMessage && (
        <p className="twofa-error" role="alert">
          {errorMessage}
        </p>
      )}

      <input
        className="search-bar"
        type="password"
        autoComplete="current-password"
        aria-label="Current password"
        placeholder="Current password"
        value={currentPassword}
        onChange={e => setCurrentPassword(e.target.value)}
        disabled={isBusy}
      />
      <input
        className="search-bar"
        type="password"
        autoComplete="new-password"
        aria-label="New password"
        placeholder="New password"
        value={newPassword}
        onChange={e => setNewPassword(e.target.value)}
        disabled={isBusy}
      />
      <input
        className="search-bar"
        type="password"
        autoComplete="new-password"
        aria-label="Confirm new password"
        placeholder="Confirm new password"
        value={confirmPassword}
        onChange={e => setConfirmPassword(e.target.value)}
        disabled={isBusy}
      />

      {/* Inline guidance so the disabled Change button isn't a dead end. */}
      {newPassword.length > 0 && !isNewStrong && (
        <p className="modal__body" role="alert">
          New password doesn't meet the requirements.
        </p>
      )}
      {confirmPassword.length > 0 && !doPasswordsMatch && (
        <p className="modal__body" role="alert">
          Passwords don't match.
        </p>
      )}
      {isNewStrong && !isNewDifferent && (
        <p className="modal__body" role="alert">
          New password must be different from your current one.
        </p>
      )}

      <div className="modal__actions">
        <button type="button" className="modal__cancel" onClick={onClose} disabled={isBusy}>
          Cancel
        </button>
        <button
          type="button"
          className="modal__confirm"
          disabled={!canSubmit}
          onClick={handleChange}
        >
          Change Password
        </button>
      </div>
    </Modal>
  )
}

