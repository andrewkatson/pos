import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import type { UserSearchResult } from '../api/types'
import Avatar from '../components/Avatar'
import './MainApp.css'

/**
 * "Blocked Users": everyone the signed-in user has blocked, each with an
 * Unblock button (toggle_block). Mirrors the iOS BlockedUsersView and the
 * Android BlockedUsersScreen.
 */
function BlockedUsersPage() {
  if (!apiClient.isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return <BlockedUsersView />
}

function BlockedUsersView() {
  const navigate = useNavigate()
  const isMounted = useRef(true)
  useEffect(() => {
    isMounted.current = true
    return () => {
      isMounted.current = false
    }
  }, [])

  const [blockedUsers, setBlockedUsers] = useState<UserSearchResult[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  // The usernames with an unblock request in flight, so each row's button can
  // be disabled independently (several unblocks may overlap).
  const [unblocking, setUnblocking] = useState<ReadonlySet<string>>(new Set())

  const load = useCallback(async () => {
    try {
      if (isMounted.current) setErrorMessage(null) // drop any stale error before reloading
      const users = await apiClient.getBlockedUsers()
      if (!isMounted.current) return
      setBlockedUsers(users)
    } catch (err) {
      if (isMounted.current) setErrorMessage((err as ApiError).message ?? 'Failed to load.')
    } finally {
      if (isMounted.current) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void Promise.resolve().then(load)
  }, [load])

  async function unblock(username: string) {
    setUnblocking(current => new Set(current).add(username))
    setErrorMessage(null)
    try {
      await apiClient.toggleBlock(username)
      if (!isMounted.current) return
      setBlockedUsers(users => users.filter(user => user.username !== username))
    } catch (err) {
      if (isMounted.current)
        setErrorMessage((err as ApiError).message ?? 'Failed to unblock user.')
    } finally {
      if (isMounted.current)
        setUnblocking(current => {
          const next = new Set(current)
          next.delete(username)
          return next
        })
    }
  }

  return (
    <div className="app-shell">
      <header className="app-bar">
        <button type="button" className="app-bar__back" onClick={() => navigate(-1)}>
          ← Back
        </button>
        <h1 className="app-bar__title">Blocked Users</h1>
      </header>

      <main className="app-content">
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

        {isLoading ? (
          <div className="center-spinner">
            <span className="spinner" />
          </div>
        ) : (
          <section className="settings-group">
            {blockedUsers.length === 0 && (
              <p className="muted">You haven't blocked anyone.</p>
            )}
            <div className="user-list">
              {blockedUsers.map(user => (
                <div key={user.username} className="user-list__item">
                  <Avatar
                    src={user.author_profile_image_url}
                    originalSrc={user.author_profile_image_original_url}
                    username={user.username}
                    size="sm"
                  />
                  <span className="user-list__name">{user.username}</span>
                  {user.identity_is_verified && (
                    <span className="verified-badge" aria-label="Verified">
                      ✓
                    </span>
                  )}
                  <button
                    type="button"
                    className="btn btn-primary appeal-item__action"
                    disabled={unblocking.has(user.username)}
                    onClick={() => void unblock(user.username)}
                  >
                    Unblock
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  )
}

export default BlockedUsersPage
