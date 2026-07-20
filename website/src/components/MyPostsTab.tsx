import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import { getCurrentUsername } from '../api/session'
import type { FeedPost, PostStatusResponse, UserSearchResult } from '../api/types'
import PostThumbnail from './PostThumbnail'

/** How often the bounded post-classification poll checks pending posts (#282). */
const STATUS_POLL_INTERVAL_MS = 3000
/** Poll budget: ~30s of checks after which reconciliation falls back to the
 * user's own Refresh (there is deliberately no standing timer in this app). */
const STATUS_POLL_MAX_ATTEMPTS = 10
/** At most this many pending posts are polled per round, keeping the worst
 * case (3 posts every 3s = 60 requests/min) inside the status endpoint's
 * 120/m per-user rate limit; older pending posts reconcile on refresh. */
const STATUS_POLL_MAX_POSTS = 3

/** Overlay label for the author's own pending/rejected grid tiles (#282). */
function statusBadgeLabel(post: FeedPost): string | null {
  if (post.status === 'pending') return 'In review'
  if (post.status === 'rejected') return 'Hidden — you can appeal'
  return null
}

/**
 * The "Home" tab: the signed-in user's own post grid, with a user-search bar
 * that swaps the grid for a results list. Mirrors iOS MyPostsGridView +
 * HomeViewModel (debounced search, 3-char minimum, paginated post grid).
 *
 * Post classification is asynchronous (issue #282): a just-shared post appears
 * here with an "In review" badge, and a short bounded poll reconciles the
 * outcome (approved posts lose the badge; rejected ones surface a notice).
 * After the poll budget is spent, the mount/Refresh reload picks up the state.
 */
function MyPostsTab() {
  const navigate = useNavigate()
  const username = getCurrentUsername()

  // Track mount state so async loads that resolve after the tab is switched
  // away (HomePage unmounts inactive tabs) don't set state on an unmounted view.
  const isMounted = useRef(true)
  useEffect(() => {
    isMounted.current = true
    return () => {
      isMounted.current = false
    }
  }, [])

  const [posts, setPosts] = useState<FeedPost[]>([])
  const [page, setPage] = useState(0)
  const [canLoadMore, setCanLoadMore] = useState(true)
  // Start in the loading state on mount so the spinner shows without a
  // synchronous setState inside the fetch effect (which React flags).
  const [isLoading, setIsLoading] = useState(!!username)

  const [searchText, setSearchText] = useState('')
  const [searchResults, setSearchResults] = useState<UserSearchResult[]>([])

  // Reconciling async classification (#282): a bounded number of status polls
  // after a pending post is seen, plus a dismissible notice for rejections.
  const pollAttempts = useRef(0)
  const [pollTick, setPollTick] = useState(0)
  const [reviewNotice, setReviewNotice] = useState<string | null>(null)

  const loadPosts = useCallback(
    async (pageToLoad: number, replace: boolean) => {
      if (!username) {
        // Clear the loading flag so a Refresh click (which sets it true) can't
        // leave the button disabled and the spinner stuck when there's no user.
        if (isMounted.current) setIsLoading(false)
        return
      }
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
        if (isMounted.current) setIsLoading(false)
      }
    },
    [username],
  )

  // Kick the initial load off a microtask so the fetch's setState calls don't
  // run synchronously inside the effect (React flags that as cascading renders).
  useEffect(() => {
    void Promise.resolve().then(() => loadPosts(0, true))
  }, [loadPosts])

  // Short bounded poll while any of the user's posts is pending classification
  // (#282). Runs only while this tab is mounted, stops as soon as nothing is
  // pending or the budget is spent; the ordinary mount/Refresh reload is the
  // backstop after that.
  useEffect(() => {
    // The grid is newest-first, so this polls the most recent pending posts.
    const pendingPosts = posts.filter(p => p.status === 'pending').slice(0, STATUS_POLL_MAX_POSTS)
    if (pendingPosts.length === 0 || pollAttempts.current >= STATUS_POLL_MAX_ATTEMPTS) return
    const id = setTimeout(async () => {
      pollAttempts.current += 1
      try {
        const results = await Promise.allSettled(
          pendingPosts.map(p => apiClient.getPostStatus(p.post_identifier)),
        )
        if (!isMounted.current) return
        const statuses = results
          .filter((r): r is PromiseFulfilledResult<PostStatusResponse> => r.status === 'fulfilled')
          .map(r => r.value)
        const resolved = statuses.filter(s => s.status !== 'pending')
        if (resolved.length > 0) {
          const rejection = resolved.find(
            s => s.status === 'rejected' || s.status === 'rejected_final',
          )
          if (rejection) {
            setReviewNotice(
              rejection.message ?? 'One of your recent posts did not pass automated review.',
            )
          }
          // Reload from the server so the grid reflects the resolved state
          // (approved posts lose the badge; final rejections drop out).
          void loadPosts(0, true)
        } else {
          // Nothing resolved yet: re-arm the timer by bumping the tick.
          setPollTick(t => t + 1)
        }
      } catch {
        // A failed poll round just ends this cycle; Refresh remains available.
      }
    }, STATUS_POLL_INTERVAL_MS)
    return () => clearTimeout(id)
  }, [posts, pollTick, loadPosts])

  // Debounced user search (500ms), only firing for 3+ character queries. The
  // setState lives in the timeout callback (not synchronously in the effect);
  // clearing for short queries is handled in the input's onChange below.
  useEffect(() => {
    const query = searchText.trim()
    if (query.length < 3) return
    const id = setTimeout(async () => {
      try {
        const results = await apiClient.searchUsers(query)
        if (isMounted.current) setSearchResults(results)
      } catch {
        if (isMounted.current) setSearchResults([])
      }
    }, 500)
    return () => clearTimeout(id)
  }, [searchText])

  function handleSearchChange(value: string) {
    setSearchText(value)
    if (value.trim().length < 3) setSearchResults([])
  }

  const isSearching = searchText.trim().length > 0

  return (
    <div>
      <input
        className="search-bar"
        type="search"
        placeholder="Search for Users"
        aria-label="Search for users"
        autoCapitalize="none"
        value={searchText}
        onChange={e => handleSearchChange(e.target.value)}
      />

      {isSearching ? (
        <div className="user-list">
          {searchResults.map(user => (
            <button
              key={user.username}
              type="button"
              className="user-list__item"
              onClick={() => navigate(`/profile/${encodeURIComponent(user.username)}`)}
            >
              <span className="user-list__avatar" aria-hidden="true">
                ◍
              </span>
              <span className="user-list__name">{user.username}</span>
              {user.identity_is_verified && (
                <span className="verified-badge" aria-label="Verified">
                  ✓
                </span>
              )}
            </button>
          ))}
          {searchText.trim().length >= 3 && searchResults.length === 0 && (
            <p className="muted">No users found.</p>
          )}
        </div>
      ) : (
        <>
          <button
            type="button"
            className="refresh-button"
            aria-label="Refresh"
            disabled={isLoading}
            onClick={() => {
              setIsLoading(true)
              // A manual refresh grants a fresh reconcile-poll budget (#282).
              pollAttempts.current = 0
              void loadPosts(0, true)
            }}
          >
            <span aria-hidden="true">↻</span> Refresh
          </button>

          {reviewNotice && (
            <div className="auth-error" role="alert">
              <p>{reviewNotice}</p>
              <button
                type="button"
                className="auth-error__dismiss"
                aria-label="Dismiss notice"
                onClick={() => setReviewNotice(null)}
              >
                ✕
              </button>
            </div>
          )}

          {posts.length === 0 && !isLoading ? (
            <p className="muted">You haven't posted anything yet.</p>
          ) : (
            <div className="post-grid">
              {posts.map(post => {
                const badge = statusBadgeLabel(post)
                return (
                  <button
                    key={post.post_identifier}
                    type="button"
                    className="post-grid__cell"
                    // The explicit aria-label overrides the accessible-name
                    // calculation, so the review state must be part of it for
                    // assistive tech to announce it (the visual badge below is
                    // otherwise invisible to screen readers).
                    aria-label={
                      badge
                        ? `Post by ${post.author_username} — ${badge}`
                        : `Post by ${post.author_username}`
                    }
                    onClick={() => navigate(`/post/${post.post_identifier}`)}
                  >
                    <PostThumbnail post={post} />
                    {badge && <span className="post-grid__status-badge">{badge}</span>}
                  </button>
                )
              })}
            </div>
          )}
          {isLoading && <div className="center-spinner"><span className="spinner" /></div>}
          {canLoadMore && !isLoading && posts.length > 0 && (
            <button
              type="button"
              className="load-more"
              onClick={() => {
                setIsLoading(true)
                void loadPosts(page, false)
              }}
            >
              Load more
            </button>
          )}
        </>
      )}
    </div>
  )
}

export default MyPostsTab
