import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { apiClient } from '../api/client'
import { getCurrentUsername } from '../api/session'
import type { FeedPost } from '../api/types'
import PostGrid from '../components/PostGrid'
import './MainApp.css'

/**
 * The /tags/:tag route (issue #379): a back bar over a paginated grid of the
 * posts carrying that hashtag, newest first. The backend applies the usual
 * visibility and block rules, so this only ever shows posts the viewer is
 * allowed to see.
 *
 * The inner grid is keyed by tag so navigating between tags fully resets state
 * instead of briefly showing the previous tag's posts.
 */
function TagPage() {
  const { tag = '' } = useParams<{ tag: string }>()
  const navigate = useNavigate()

  if (!apiClient.isAuthenticated()) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="app-shell">
      <header className="app-bar">
        <button type="button" className="app-bar__back" onClick={() => navigate(-1)}>
          ← Back
        </button>
        <h1 className="app-bar__title">#{tag}</h1>
      </header>

      <main className="app-content">
        <TagFeed key={tag} tag={tag} currentUsername={getCurrentUsername()} />
      </main>
    </div>
  )
}

interface TagFeedProps {
  tag: string
  currentUsername: string | null
}

function TagFeed({ tag, currentUsername }: TagFeedProps) {
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

  const loadPosts = useCallback(
    async (pageToLoad: number, replace: boolean) => {
      try {
        const newPosts = await apiClient.getPostsByTag(tag, pageToLoad)
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
    [tag],
  )

  // Deferred to a microtask so the fetch's setState calls don't run
  // synchronously inside the effect (matches ProfileView).
  useEffect(() => {
    void Promise.resolve().then(() => loadPosts(0, true))
  }, [loadPosts])

  const handlePostDeleted = useCallback((postIdentifier: string) => {
    setPosts(prev => prev.filter(p => p.post_identifier !== postIdentifier))
  }, [])

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

      {posts.length === 0 && !isLoading ? (
        <p className="muted">No posts with #{tag} yet.</p>
      ) : (
        <PostGrid
          posts={posts}
          currentUsername={currentUsername}
          onPostDeleted={handlePostDeleted}
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
            void loadPosts(page, false)
          }}
        >
          Load more
        </button>
      )}
    </>
  )
}

export default TagPage
