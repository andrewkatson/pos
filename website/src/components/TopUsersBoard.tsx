import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { apiClient } from '../api/client'
import type { TopUser } from '../api/types'
import { profilePathFor } from '../utils/profilePath'
import Avatar from './Avatar'

function followerLabel(count: number): string {
  return count === 1 ? '1 follower' : `${count.toLocaleString()} followers`
}

/**
 * The most-followed people board (issue #562): the Top feed's "People" view,
 * ranking who has the most followers right now. Each row opens that profile.
 */
function TopUsersBoard() {
  const navigate = useNavigate()
  const [users, setUsers] = useState<TopUser[]>([])
  const [page, setPage] = useState(0)
  const [canLoadMore, setCanLoadMore] = useState(true)
  const [isLoading, setIsLoading] = useState(true)

  // Same guards as FeedTab: ignore loads that land after unmount or after a
  // newer from-scratch load, and remember who is listed so a live page that
  // only repeats people doesn't stall "Load more".
  const isMounted = useRef(true)
  const loadGeneration = useRef(0)
  const listed = useRef(new Set<string>())
  useEffect(() => {
    isMounted.current = true
    return () => {
      isMounted.current = false
    }
  }, [])

  const load = useCallback(async (pageToLoad: number, replace: boolean) => {
    if (replace) loadGeneration.current += 1
    const generation = loadGeneration.current
    const isCurrent = () => isMounted.current && generation === loadGeneration.current
    try {
      let nextPage = pageToLoad
      for (;;) {
        const batch = await apiClient.getTopUsers(nextPage)
        if (!isCurrent()) return
        if (replace) {
          listed.current = new Set(batch.map(user => user.username))
          setUsers(batch)
          setCanLoadMore(batch.length > 0)
          setPage(batch.length > 0 ? 1 : 0)
          break
        }
        if (batch.length === 0) {
          setCanLoadMore(false)
          break
        }
        const unseen = batch.filter(user => !listed.current.has(user.username))
        nextPage += 1
        setPage(nextPage)
        if (unseen.length > 0) {
          unseen.forEach(user => listed.current.add(user.username))
          setUsers(prev => [...prev, ...unseen])
          break
        }
      }
    } catch {
      if (isCurrent()) setCanLoadMore(false)
    } finally {
      if (isCurrent()) setIsLoading(false)
    }
  }, [])

  // Deferred to a microtask so the fetch's setState calls don't run
  // synchronously inside the effect, as in FeedTab.
  useEffect(() => {
    void Promise.resolve().then(() => load(0, true))
  }, [load])

  return (
    <div>
      <button
        type="button"
        className="refresh-button"
        aria-label="Refresh"
        disabled={isLoading}
        onClick={() => {
          setIsLoading(true)
          void load(0, true)
        }}
      >
        <span aria-hidden="true">↻</span> Refresh
      </button>

      {users.length === 0 && !isLoading ? (
        <p className="muted">Nobody to rank yet.</p>
      ) : (
        <div className="user-list">
          {users.map((user, index) => (
            <button
              key={user.username}
              type="button"
              className="user-list__item"
              onClick={() => navigate(profilePathFor(user.username))}
            >
              <span className="feed-post__rank" aria-label={`Rank ${index + 1}`}>
                #{index + 1}
              </span>
              <Avatar
                src={user.author_profile_image_url}
                originalSrc={user.author_profile_image_original_url}
                blurhash={user.author_profile_image_blurhash}
                username={user.username}
                size="sm"
              />
              <span className="user-list__name">{user.username}</span>
              {user.identity_is_verified && (
                <span className="verified-badge" aria-label="Verified">
                  ✓
                </span>
              )}
              <span className="user-list__count muted">{followerLabel(user.follower_count)}</span>
            </button>
          ))}
        </div>
      )}

      {isLoading && <div className="center-spinner"><span className="spinner" /></div>}
      {canLoadMore && !isLoading && users.length > 0 && (
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
    </div>
  )
}

export default TopUsersBoard
