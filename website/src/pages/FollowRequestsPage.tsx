import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import type { UserSearchResult } from '../api/types'
import Avatar from '../components/Avatar'
import './MainApp.css'

/**
 * "Follow Requests" (issue #96): everyone waiting to follow the signed-in
 * private account, newest first, each with Approve and Deny. Mirrors the iOS
 * FollowRequestsView and the Android FollowRequestsScreen.
 */
function FollowRequestsPage() {
  if (!apiClient.isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return <FollowRequestsView />
}

function FollowRequestsView() {
  const navigate = useNavigate()
  const isMounted = useRef(true)
  useEffect(() => {
    isMounted.current = true
    return () => {
      isMounted.current = false
    }
  }, [])

  const [requests, setRequests] = useState<UserSearchResult[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  // Usernames with an approve/deny in flight, so each row's buttons disable
  // independently (several decisions may overlap).
  const [deciding, setDeciding] = useState<ReadonlySet<string>>(new Set())

  const load = useCallback(async () => {
    try {
      if (isMounted.current) setErrorMessage(null)
      const users = await apiClient.getFollowRequests()
      if (!isMounted.current) return
      setRequests(users)
    } catch (err) {
      if (isMounted.current) setErrorMessage((err as ApiError).message ?? 'Failed to load.')
    } finally {
      if (isMounted.current) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void Promise.resolve().then(load)
  }, [load])

  async function decide(username: string, approve: boolean) {
    setDeciding(current => new Set(current).add(username))
    setErrorMessage(null)
    try {
      if (approve) await apiClient.approveFollowRequest(username)
      else await apiClient.denyFollowRequest(username)
      if (!isMounted.current) return
      setRequests(users => users.filter(user => user.username !== username))
    } catch (err) {
      if (isMounted.current)
        setErrorMessage(
          (err as ApiError).message ??
            (approve ? 'Failed to approve request.' : 'Failed to deny request.'),
        )
    } finally {
      if (isMounted.current)
        setDeciding(current => {
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
        <h1 className="app-bar__title">Follow Requests</h1>
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
            {requests.length === 0 && <p className="muted">No one is waiting to follow you.</p>}
            <div className="user-list">
              {requests.map(user => (
                <div key={user.username} className="user-list__item">
                  <Avatar
                    src={user.author_profile_image_url}
                    originalSrc={user.author_profile_image_original_url}
                    blurhash={user.author_profile_image_blurhash}
                    username={user.username}
                    size="sm"
                  />
                  <Link className="user-list__name" to={`/profile/${user.username}`}>
                    {user.username}
                  </Link>
                  {user.identity_is_verified && (
                    <span className="verified-badge" aria-label="Verified">
                      ✓
                    </span>
                  )}
                  <button
                    type="button"
                    className="btn btn-primary appeal-item__action"
                    disabled={deciding.has(user.username)}
                    aria-label={`Approve ${user.username}`}
                    onClick={() => void decide(user.username, true)}
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline appeal-item__action"
                    disabled={deciding.has(user.username)}
                    aria-label={`Deny ${user.username}`}
                    onClick={() => void decide(user.username, false)}
                  >
                    Deny
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

export default FollowRequestsPage
