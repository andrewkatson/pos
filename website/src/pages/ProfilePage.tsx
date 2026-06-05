import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { FeedPost, ProfileDetails } from '../api/types'
import './MainApp.css'

/**
 * A user's profile: stats, follow/block actions, and their post grid. Mirrors
 * iOS ProfileView / ProfileViewModel (optimistic follow/block, paginated grid).
 *
 * The inner view is keyed by username so navigating between profiles fully
 * resets its state instead of briefly showing the previous user's data.
 */
function ProfilePage() {
  const { username = '' } = useParams<{ username: string }>()
  // This view hits authenticated endpoints, so require a session like HomePage.
  if (!apiClient.isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return <ProfileView key={username} username={username} />
}

function ProfileView({ username }: { username: string }) {
  const navigate = useNavigate()

  // Track mount state so async loads that resolve after navigating away don't
  // set state on an unmounted view.
  const isMounted = useRef(true)
  useEffect(() => {
    isMounted.current = true
    return () => {
      isMounted.current = false
    }
  }, [])

  const [profile, setProfile] = useState<ProfileDetails | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [isFollowing, setIsFollowing] = useState(false)
  const [isBlocked, setIsBlocked] = useState(false)
  const [isBusy, setIsBusy] = useState(false)

  const [posts, setPosts] = useState<FeedPost[]>([])
  const [page, setPage] = useState(0)
  const [canLoadMore, setCanLoadMore] = useState(true)
  // Start loading so the spinner shows on mount without a synchronous setState
  // inside the fetch effect.
  const [isLoadingPosts, setIsLoadingPosts] = useState(true)

  useEffect(() => {
    let cancelled = false
    apiClient
      .getProfile(username)
      .then(details => {
        if (cancelled) return
        setProfile(details)
        setIsFollowing(details.is_following)
        setIsBlocked(details.is_blocked)
      })
      .catch(() => {
        // Couldn't load the profile (e.g. user not found) — show a message.
        if (!cancelled) setNotFound(true)
      })
    return () => {
      cancelled = true
    }
  }, [username])

  const loadPosts = useCallback(
    async (pageToLoad: number, replace: boolean) => {
      try {
        const newPosts = await apiClient.getPostsForUser(username, pageToLoad)
        if (!isMounted.current) return
        if (replace) {
          setPosts(newPosts)
          setCanLoadMore(newPosts.length > 0)
          setPage(newPosts.length > 0 ? 1 : 0)
        } else if (newPosts.length === 0) {
          setCanLoadMore(false)
        } else {
          setPosts(prev => [...prev, ...newPosts])
          setPage(prev => prev + 1)
        }
      } catch {
        if (isMounted.current) setCanLoadMore(false)
      } finally {
        if (isMounted.current) setIsLoadingPosts(false)
      }
    },
    [username],
  )

  // Deferred to a microtask so the fetch's setState calls don't run
  // synchronously inside the effect (React flags that as cascading renders).
  useEffect(() => {
    void Promise.resolve().then(() => loadPosts(0, true))
  }, [loadPosts])

  async function toggleFollow() {
    if (isBusy) return
    setIsBusy(true)
    const wasFollowing = isFollowing
    try {
      if (wasFollowing) {
        await apiClient.unfollowUser(username)
        setIsFollowing(false)
        setProfile(p => (p ? { ...p, follower_count: Math.max(0, p.follower_count - 1) } : p))
      } else {
        await apiClient.followUser(username)
        setIsFollowing(true)
        setProfile(p => (p ? { ...p, follower_count: p.follower_count + 1 } : p))
      }
    } catch {
      /* state is only updated after a successful call, so nothing to revert */
    } finally {
      setIsBusy(false)
    }
  }

  async function toggleBlock() {
    if (isBusy) return
    setIsBusy(true)
    const wasFollowing = isFollowing
    try {
      await apiClient.toggleBlock(username)
      const nowBlocked = !isBlocked
      setIsBlocked(nowBlocked)
      // Blocking severs the follow relationship on the backend; reflect that in
      // the follow button and the follower count so the stats stay consistent.
      if (nowBlocked && wasFollowing) {
        setIsFollowing(false)
        setProfile(p => (p ? { ...p, follower_count: Math.max(0, p.follower_count - 1) } : p))
      }
    } catch {
      /* state is only updated after a successful call, so nothing to revert */
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="app-bar">
        <button type="button" className="app-bar__back" onClick={() => navigate(-1)}>
          ← Back
        </button>
        <h1 className="app-bar__title">{username}</h1>
      </header>

      {notFound ? (
        <main className="app-content">
          <p className="muted">User not found.</p>
        </main>
      ) : (
      <main className="app-content">
        <div className="profile-header">
          <div className="profile-stats">
            <div>
              <span className="profile-stat__count">{profile?.post_count ?? posts.length}</span>
              <span className="profile-stat__label">Posts</span>
            </div>
            <div>
              <span className="profile-stat__count">{profile?.follower_count ?? 0}</span>
              <span className="profile-stat__label">Followers</span>
            </div>
            <div>
              <span className="profile-stat__count">{profile?.following_count ?? 0}</span>
              <span className="profile-stat__label">Following</span>
            </div>
          </div>

          <div className="profile-actions">
            <button
              type="button"
              className={`btn ${isFollowing ? 'btn-outline' : 'btn-primary'}`}
              disabled={isBusy}
              onClick={toggleFollow}
            >
              {isFollowing ? 'Following' : 'Follow'}
            </button>
            <button
              type="button"
              className={`btn ${isBlocked ? 'btn-danger--filled' : 'btn-danger'}`}
              disabled={isBusy}
              onClick={toggleBlock}
            >
              {isBlocked ? 'Unblock' : 'Block'}
            </button>
          </div>
        </div>

        {posts.length === 0 && !isLoadingPosts ? (
          <p className="muted">{username} hasn't posted anything yet.</p>
        ) : (
          <div className="post-grid">
            {posts.map(post => (
              <button
                key={post.post_identifier}
                type="button"
                className="post-grid__cell"
                aria-label={`Post by ${post.author_username}`}
                onClick={() => navigate(`/post/${post.post_identifier}`)}
              >
                <img src={post.image_url} alt={post.caption} />
              </button>
            ))}
          </div>
        )}

        {isLoadingPosts && (
          <div className="center-spinner">
            <span className="spinner" />
          </div>
        )}
        {canLoadMore && !isLoadingPosts && posts.length > 0 && (
          <button
            type="button"
            className="load-more"
            onClick={() => {
              setIsLoadingPosts(true)
              void loadPosts(page, false)
            }}
          >
            Load more
          </button>
        )}
      </main>
      )}
    </div>
  )
}

export default ProfilePage
