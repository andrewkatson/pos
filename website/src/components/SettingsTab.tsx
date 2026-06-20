import { useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import { clearSession } from '../api/session'
import { PRIVACY_POLICY_TEXT } from '../pages/RegisterPage'

type ActiveModal = 'logout' | 'delete' | 'verify' | 'privacy' | null

const CONTACT_EMAIL = 'katsonsoftware@gmail.com'

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
        <div className="settings-row settings-row--static">{CONTACT_EMAIL}</div>
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
          onClick={() => navigate('/appeals')}
        >
          Hidden Content &amp; Appeals
        </button>
        <button
          type="button"
          className="settings-row"
          onClick={() => setActiveModal('privacy')}
        >
          Privacy Policy
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

interface ModalProps {
  title: string
  body?: string
  children: ReactNode
}

function Modal({ title, body, children }: ModalProps) {
  return (
    <div className="modal-overlay">
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <h2 className="modal__title">{title}</h2>
        {body && <p className="modal__body">{body}</p>}
        {children}
      </div>
    </div>
  )
}

export default SettingsTab
