import { useCallback, useEffect, useRef, useState } from 'react'
import { apiClient } from '../api/client'
import type { FeedPost, ProfileDetails } from '../api/types'
import PostGrid from './PostGrid'

interface ProfileViewProps {
  username: string
  /** Hides the follow/block actions, which don't apply to your own account. */
  isOwnProfile: boolean
  /** The signed-in user, passed to the grid so it can offer Delete on own posts. */
  currentUsername: string | null
}

/**
 * A user's profile body: stats, follow/block actions, and their post grid.
 * Mirrors iOS ProfileView / ProfileViewModel (optimistic follow/block,
 * paginated grid).
 *
 * Shared by the Profile tab (your own account, reached from the bottom bar per
 * issue #347) and the /profile/:username route (anyone else), so both render an
 * identical profile and the same in-place post actions.
 */
function ProfileView({ username, isOwnProfile, currentUsername }: ProfileViewProps) {
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
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

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

  // Manual refresh reloads both the posts and the profile details
  // (follow/block/counts) so the whole view stays in sync — not just the grid.
  function refresh() {
    setIsLoadingPosts(true)
    apiClient
      .getProfile(username)
      .then(details => {
        if (!isMounted.current) return
        setProfile(details)
        setIsFollowing(details.is_following)
        setIsBlocked(details.is_blocked)
      })
      .catch(() => {
        // Keep the already-loaded details on a transient refresh failure rather
        // than blanking the profile or flipping to "not found".
      })
    void loadPosts(0, true)
  }

  // Deleting from the grid drops the post locally and decrements the stat, so
  // the count doesn't contradict the grid until the next refresh (issue #267).
  function handlePostDeleted(postIdentifier: string) {
    setPosts(prev => prev.filter(post => post.post_identifier !== postIdentifier))
    setProfile(p => (p ? { ...p, post_count: Math.max(0, p.post_count - 1) } : p))
  }

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

  if (notFound) {
    return <p className="muted">User not found.</p>
  }

  return (
    <>
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

        {!isOwnProfile && (
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
        )}
      </div>

      <button
        type="button"
        className="refresh-button"
        aria-label="Refresh"
        disabled={isLoadingPosts}
        onClick={refresh}
      >
        <span aria-hidden="true">↻</span> Refresh
      </button>

      {posts.length === 0 && !isLoadingPosts ? (
        <p className="muted">
          {isOwnProfile ? "You haven't posted anything yet." : `${username} hasn't posted anything yet.`}
        </p>
      ) : (
        <PostGrid
          posts={posts}
          currentUsername={currentUsername}
          onPostDeleted={handlePostDeleted}
          onError={setErrorMessage}
        />
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
    </>
  )
}

export default ProfileView
