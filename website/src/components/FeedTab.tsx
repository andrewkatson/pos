import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { FeedPost } from '../api/types'
import PostThumbnail from './PostThumbnail'

type FeedType = 'forYou' | 'following'

/**
 * The "Feed" tab with a For You / Following segmented control. Each feed loads
 * independently and supports pagination. Mirrors iOS FeedView (ForYou +
 * Following feeds, infinite scroll, tap author → profile, tap image → detail).
 */
function FeedTab() {
  const navigate = useNavigate()
  const [selected, setSelected] = useState<FeedType>('forYou')

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
  // Start loading on mount so the spinner shows without a synchronous setState
  // inside the fetch effect (which React flags as a cascading render).
  const [isLoading, setIsLoading] = useState(true)

  const fetcher = useCallback(
    (batch: number) =>
      selected === 'forYou' ? apiClient.getFeed(batch) : apiClient.getFollowedFeed(batch),
    [selected],
  )

  const loadFeed = useCallback(
    async (pageToLoad: number, replace: boolean) => {
      try {
        const newPosts = await fetcher(pageToLoad)
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
    [fetcher],
  )

  // Reload from scratch whenever the selected feed changes. Deferred to a
  // microtask so the fetch's setState calls don't run synchronously inside the
  // effect (React flags that as cascading renders).
  useEffect(() => {
    void Promise.resolve().then(() => loadFeed(0, true))
  }, [loadFeed])

  return (
    <div>
      <div className="segmented" role="tablist" aria-label="Feed type">
        <button
          type="button"
          role="tab"
          aria-selected={selected === 'forYou'}
          className={`segmented__option${selected === 'forYou' ? ' segmented__option--active' : ''}`}
          onClick={() => {
            setIsLoading(true)
            setSelected('forYou')
          }}
        >
          For You
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={selected === 'following'}
          className={`segmented__option${selected === 'following' ? ' segmented__option--active' : ''}`}
          onClick={() => {
            setIsLoading(true)
            setSelected('following')
          }}
        >
          Following
        </button>
      </div>

      <button
        type="button"
        className="refresh-button"
        aria-label="Refresh"
        disabled={isLoading}
        onClick={() => {
          setIsLoading(true)
          void loadFeed(0, true)
        }}
      >
        <span aria-hidden="true">↻</span> Refresh
      </button>

      {posts.length === 0 && !isLoading ? (
        <p className="muted">No posts here yet.</p>
      ) : (
        <div className="feed-list">
          {posts.map(post => (
            <article key={post.post_identifier}>
              <button
                type="button"
                className="feed-post__author"
                onClick={() => navigate(`/profile/${encodeURIComponent(post.author_username)}`)}
              >
                {post.author_username}
              </button>
              <button
                type="button"
                className="feed-post__image"
                aria-label={`Open post by ${post.author_username}`}
                onClick={() => navigate(`/post/${post.post_identifier}`)}
              >
                <PostThumbnail post={post} />
              </button>
            </article>
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
            void loadFeed(page, false)
          }}
        >
          Load more
        </button>
      )}
    </div>
  )
}

export default FeedTab
