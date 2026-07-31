import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { apiClient } from '../api/client'
import { clearSession } from '../api/session'
import type { CurrentUser, NotificationPreference } from '../api/types'
import { PRIVACY_POLICY_TEXT } from '../privacyPolicy'
import Modal from './Modal'
import {
  ChangePasswordModal,
  DisableTwoFactorModal,
  EnableTwoFactorModal,
} from './TwoFactorAuthModals'

type ActiveModal =
  | 'logout'
  | 'delete'
  | 'verify'
  | 'privacy'
  | 'enable2fa'
  | 'disable2fa'
  | 'changePassword'
  | null

/** Support address shown under "Contact Us" for feedback and help (issue #194). */
const SUPPORT_EMAIL = 'katsonsoftware@gmail.com'

/**
 * The "Settings" tab: contact info, logout, identity verification, privacy
 * policy, and account deletion — with confirmation dialogs. Mirrors iOS
 * SettingsView / SettingsViewModel.
 */
function SettingsTab() {
  const navigate = useNavigate()
  const [activeModal, setActiveModal] = useState<ActiveModal>(null)
  const [dateOfBirth, setDateOfBirth] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [infoMessage, setInfoMessage] = useState<string | null>(null)
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [notifPrefs, setNotifPrefs] = useState<NotificationPreference[]>([])
  // Types with a save in flight (#342/#343): their row is disabled and a
  // re-click is ignored, so concurrent saves for one type can't race.
  const [savingTypes, setSavingTypes] = useState<string[]>([])

  // Load the signed-in account's own username + email for the Contact
  // Information section (load-on-mount, matching the rest of the app).
  useEffect(() => {
    let cancelled = false
    apiClient
      .getCurrentUser()
      .then(user => {
        if (!cancelled) setCurrentUser(user)
      })
      .catch(() => {
        // Non-fatal: the section falls back to a placeholder if this fails.
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Load the push notification toggles (issues #342/#343). One row per type the
  // backend reports, so a new type appears here with no client change.
  useEffect(() => {
    let cancelled = false
    apiClient
      .getNotificationPreferences()
      .then(prefs => {
        if (!cancelled) setNotifPrefs(prefs)
      })
      .catch(() => {
        // Non-fatal: the section just doesn't render if this fails.
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function toggleNotification(pref: NotificationPreference) {
    // Serialize per type: ignore a re-click while this type's save is in flight
    // (the row is also disabled), so out-of-order responses can't leave the UI
    // or the backend on an unintended value.
    if (savingTypes.includes(pref.type)) return
    const next = !pref.enabled
    // Clear any error from a previous failed toggle so the banner only ever
    // reflects the most recent attempt.
    setErrorMessage(null)
    // Optimistic: flip immediately, revert on failure.
    setNotifPrefs(prev => prev.map(p => (p.type === pref.type ? { ...p, enabled: next } : p)))
    setSavingTypes(prev => [...prev, pref.type])
    try {
      await apiClient.setNotificationPreference(pref.type, next)
    } catch {
      setNotifPrefs(prev => prev.map(p => (p.type === pref.type ? { ...p, enabled: !next } : p)))
      setErrorMessage('Could not update notification settings. Please try again.')
    } finally {
      setSavingTypes(prev => prev.filter(t => t !== pref.type))
    }
  }

  const close = () => setActiveModal(null)

  async function handleLogout() {
    close()
    try {
      await apiClient.logout()
    } catch {
      // Even if the backend call fails, log out locally (mirrors the native apps).
    }
    clearSession()
    navigate('/')
  }

  async function handleDelete() {
    close()
    try {
      await apiClient.deleteAccount()
      clearSession()
      navigate('/')
    } catch {
      setErrorMessage('Failed to delete account. Please try again.')
    }
  }

  async function handleVerify() {
    close()
    try {
      await apiClient.verifyIdentity(dateOfBirth)
      setInfoMessage('Identity verified successfully!')
    } catch {
      setErrorMessage('Verification failed. Please check your date of birth.')
    }
  }

  return (
    <div className="settings-list">
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
      {infoMessage && (
        <div className="auth-success" role="status">
          {infoMessage}
        </div>
      )}

      <div className="settings-group">
        <span className="settings-group__header">Contact Information</span>
        <div className="settings-row settings-row--static">
          {currentUser ? currentUser.username : '…'}
        </div>
        <div className="settings-row settings-row--static">
          {currentUser ? currentUser.email : '…'}
        </div>
      </div>

      <div className="settings-group">
        <span className="settings-group__header">Contact Us</span>
        <a className="settings-row settings-row--static" href={`mailto:${SUPPORT_EMAIL}`}>
          {SUPPORT_EMAIL}
        </a>
      </div>

      <div className="settings-group">
        <button
          type="button"
          className="settings-row settings-row--destructive"
          onClick={() => setActiveModal('logout')}
        >
          Logout
        </button>
        <button
          type="button"
          className="settings-row settings-row--action"
          onClick={() => setActiveModal('verify')}
        >
          Verify Identity
        </button>
        <button
          type="button"
          className="settings-row"
          onClick={() => navigate('/saved')}
        >
          Saved Posts
        </button>
        <button
          type="button"
          className="settings-row"
          onClick={() => navigate('/appeals')}
        >
          Hidden Content &amp; Appeals
        </button>
        <button
          type="button"
          className="settings-row"
          onClick={() => navigate('/blocked')}
        >
          Blocked Users
        </button>
        <button
          type="button"
          className="settings-row"
          onClick={() => setActiveModal('privacy')}
        >
          Privacy Policy
        </button>
      </div>

      {notifPrefs.length > 0 && (
        <div className="settings-group">
          <span className="settings-group__header">Notifications</span>
          {notifPrefs.map(pref => (
            <button
              key={pref.type}
              type="button"
              className="settings-row settings-row--toggle"
              aria-pressed={pref.enabled}
              disabled={savingTypes.includes(pref.type)}
              onClick={() => toggleNotification(pref)}
            >
              <span>{pref.label}</span>
              <span className="settings-row__value">{pref.enabled ? 'On' : 'Off'}</span>
            </button>
          ))}
        </div>
      )}

      <div className="settings-group">
        <span className="settings-group__header">Security</span>
        <button
          type="button"
          className="settings-row settings-row--action"
          onClick={() => setActiveModal('changePassword')}
        >
          Change Password
        </button>
        <button
          type="button"
          className="settings-row settings-row--action"
          onClick={() => setActiveModal('enable2fa')}
        >
          Enable Two-Factor Authentication
        </button>
        <button
          type="button"
          className="settings-row"
          onClick={() => setActiveModal('disable2fa')}
        >
          Disable Two-Factor Authentication
        </button>
      </div>

      <div className="settings-group">
        <span className="settings-group__header">Account Actions</span>
        <button
          type="button"
          className="settings-row settings-row--destructive"
          onClick={() => setActiveModal('delete')}
        >
          Delete Account
        </button>
      </div>

      {activeModal === 'logout' && (
        <Modal title="Are you sure you want to log out?">
          <div className="modal__actions">
            <button type="button" className="modal__cancel" onClick={close}>
              Cancel
            </button>
            <button type="button" className="modal__confirm" onClick={handleLogout}>
              Logout
            </button>
          </div>
        </Modal>
      )}

      {activeModal === 'delete' && (
        <Modal title="Delete Your Account?" body="This action is permanent and cannot be undone.">
          <div className="modal__actions">
            <button type="button" className="modal__cancel" onClick={close}>
              Cancel
            </button>
            <button type="button" className="modal__confirm" onClick={handleDelete}>
              Delete
            </button>
          </div>
        </Modal>
      )}

      {activeModal === 'verify' && (
        <Modal title="Verify Identity" body="Please enter your date of birth.">
          <input
            className="search-bar"
            type="date"
            aria-label="Date of birth"
            value={dateOfBirth}
            onChange={e => setDateOfBirth(e.target.value)}
          />
          <div className="modal__actions">
            <button type="button" className="modal__cancel" onClick={close}>
              Cancel
            </button>
            <button
              type="button"
              className="modal__confirm"
              disabled={dateOfBirth.length === 0}
              onClick={handleVerify}
            >
              Verify
            </button>
          </div>
        </Modal>
      )}

      {activeModal === 'enable2fa' && (
        <EnableTwoFactorModal
          onClose={close}
          onEnabled={() => {
            close()
            setInfoMessage('Two-factor authentication is now enabled.')
          }}
        />
      )}

      {activeModal === 'disable2fa' && (
        <DisableTwoFactorModal
          onClose={close}
          onDisabled={() => {
            close()
            setInfoMessage('Two-factor authentication has been disabled.')
          }}
        />
      )}

      {activeModal === 'changePassword' && (
        <ChangePasswordModal
          onClose={close}
          onChanged={() => {
            close()
            setInfoMessage('Your password has been changed.')
          }}
        />
      )}

      {activeModal === 'privacy' && (
        <Modal title="Privacy Policy" body={PRIVACY_POLICY_TEXT}>
          <div className="modal__actions">
            <button type="button" className="modal__confirm" onClick={close}>
              Ok
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}

export default SettingsTab
