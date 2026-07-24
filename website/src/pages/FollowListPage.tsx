import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import type { UserSearchResult } from '../api/types'
import { profilePathFor } from '../utils/profilePath'
import Avatar from '../components/Avatar'
import './MainApp.css'

type FollowListMode = 'followers' | 'following'

const COPY: Record<FollowListMode, { title: string; empty: string; load: () => Promise<UserSearchResult[]> }> = {
  followers: {
    title: 'Followers',
    empty: "You don't have any followers yet.",
    load: () => apiClient.getFollowers(),
  },
  following: {
    title: 'Following',
    empty: "You aren't following anyone yet.",
    load: () => apiClient.getFollowing(),
  },
}

/**
 * "Followers" / "Following": the signed-in user's own follow lists, each row a
 * tap-through to that user's profile. Only your own lists are ever shown — the
 * backend endpoints take no username, so nobody else's list can be requested
 * (issue #8). Mirrors the iOS FollowListView and the Android FollowListScreen.
 */
function FollowListPage({ mode }: { mode: FollowListMode }) {
  if (!apiClient.isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  // Keyed by mode so switching between the two routes fully resets the list.
  return <FollowListView key={mode} mode={mode} />
}

function FollowListView({ mode }: { mode: FollowListMode }) {
  const navigate = useNavigate()
  const copy = COPY[mode]

  const isMounted = useRef(true)
  useEffect(() => {
    isMounted.current = true
    return () => {
      isMounted.current = false
    }
  }, [])

  const [users, setUsers] = useState<UserSearchResult[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      if (isMounted.current) setErrorMessage(null) // drop any stale error before reloading
      const result = await copy.load()
      if (!isMounted.current) return
      setUsers(result)
    } catch (err) {
      if (isMounted.current) setErrorMessage((err as ApiError).message ?? 'Failed to load.')
    } finally {
      if (isMounted.current) setIsLoading(false)
    }
  }, [copy])

  useEffect(() => {
    void Promise.resolve().then(load)
  }, [load])

  return (
    <div className="app-shell">
      <header className="app-bar">
        <button type="button" className="app-bar__back" onClick={() => navigate(-1)}>
          ← Back
        </button>
        <h1 className="app-bar__title">{copy.title}</h1>
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
            {users.length === 0 && <p className="muted">{copy.empty}</p>}
            <div className="user-list">
              {users.map(user => (
                <button
                  key={user.username}
                  type="button"
                  className="user-list__item"
                  onClick={() => navigate(profilePathFor(user.username))}
                >
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
                </button>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  )
}

export default FollowListPage
