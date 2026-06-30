import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import { getCurrentUsername } from '../api/session'
import type { FeedPost, UserSearchResult } from '../api/types'
import PostThumbnail from './PostThumbnail'

/**
 * The "Home" tab: the signed-in user's own post grid, with a user-search bar
 * that swaps the grid for a results list. Mirrors iOS MyPostsGridView +
 * HomeViewModel (debounced search, 3-char minimum, paginated post grid).
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
              void loadPosts(0, true)
            }}
          >
            <span aria-hidden="true">↻</span> Refresh
          </button>

          {posts.length === 0 && !isLoading ? (
            <p className="muted">You haven't posted anything yet.</p>
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
                  <PostThumbnail post={post} />
                </button>
              ))}
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
