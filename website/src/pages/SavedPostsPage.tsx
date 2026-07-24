import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import { getCurrentUsername } from '../api/session'
import type { FeedPost } from '../api/types'
import PostGrid from '../components/PostGrid'
import './MainApp.css'

/**
 * "Saved Posts": the grid of posts the signed-in user has bookmarked, reachable
 * from the Settings tab (issue #193). Each tile carries the same in-place
 * actions as the profile grid; unsaving a post drops it from this list, since
 * it no longer belongs to the collection.
 */
function SavedPostsPage() {
  if (!apiClient.isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return <SavedPostsView />
}

function SavedPostsView() {
  const navigate = useNavigate()
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
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const load = useCallback(async (pageToLoad: number, replace: boolean) => {
    try {
      if (isMounted.current) setErrorMessage(null) // drop any stale error before reloading
      const newPosts = await apiClient.getSavedPosts(pageToLoad)
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
      if (isMounted.current) {
        setErrorMessage('Failed to load your saved posts.')
        setCanLoadMore(false)
      }
    } finally {
      if (isMounted.current) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void Promise.resolve().then(() => load(0, true))
  }, [load])

  const dropPost = useCallback((postIdentifier: string) => {
    setPosts(prev => prev.filter(post => post.post_identifier !== postIdentifier))
  }, [])

  return (
    <div className="app-shell">
      <header className="app-bar">
        <button type="button" className="app-bar__back" onClick={() => navigate(-1)}>
          ← Back
        </button>
        <h1 className="app-bar__title">Saved Posts</h1>
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

        {posts.length === 0 && !isLoading ? (
          <p className="muted">You haven't saved any posts yet.</p>
        ) : (
          <PostGrid
            posts={posts}
            currentUsername={getCurrentUsername()}
            onPostDeleted={dropPost}
            // Unsaving removes the post from the collection, so drop its tile.
            onPostUnsaved={dropPost}
            onError={setErrorMessage}
          />
        )}

        {isLoading && (
          <div className="center-spinner">
            <span className="spinner" />
          </div>
        )}
        {canLoadMore && !isLoading && posts.length > 0 && (
          <button
            type="button"
            className="load-more"
            onClick={() => {
              setIsLoading(true)
              void load(page, false)
            }}
          >
            Load more
          </button>
        )}
      </main>
    </div>
  )
}

export default SavedPostsPage
