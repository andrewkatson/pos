import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { apiClient } from '../api/client'
import type { TopProfile } from '../api/types'
import { profilePathFor } from '../utils/profilePath'
import Avatar from './Avatar'
import FeedEndBanner from './FeedEndBanner'

/** "1 follower" / "12 followers". */
function followerCountLabel(count: number): string {
  return `${count.toLocaleString()} ${count === 1 ? 'follower' : 'followers'}`
}

/**
 * The Profiles half of the Feed tab's Top segment (issue #588): the public
 * accounts with the most followers, numbered by rank, each row a tap-through
 * to the profile. All-time, so unlike Top posts it has no period picker.
 * Paged with Load more like the feeds; the server stops the board at 100.
 */
function TopProfilesList() {
  const navigate = useNavigate()

  const isMounted = useRef(true)
  useEffect(() => {
    isMounted.current = true
    return () => {
      isMounted.current = false
    }
  }, [])

  const [profiles, setProfiles] = useState<TopProfile[]>([])
  const [page, setPage] = useState(0)
  const [canLoadMore, setCanLoadMore] = useState(true)
  const [reachedEnd, setReachedEnd] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  // Bumped on every refresh, so a Load more still in flight can't append the
  // old board's page to the refreshed one.
  const loadGeneration = useRef(0)
  // Usernames already listed, so live OFFSET paging can't list someone twice
  // when their rank moves between page requests (same as Top posts).
  const listed = useRef(new Set<string>())

  const load = useCallback(async (pageToLoad: number, replace: boolean) => {
    if (replace) {
      loadGeneration.current += 1
      setReachedEnd(false)
    }
    const generation = loadGeneration.current
    const isCurrent = () => isMounted.current && generation === loadGeneration.current
    try {
      let nextPage = pageToLoad
      for (;;) {
        const batch = await apiClient.getTopProfiles(nextPage)
        if (!isCurrent()) return
        if (replace) {
          listed.current = new Set(batch.map(profile => profile.username))
          setProfiles(batch)
          setCanLoadMore(batch.length > 0)
          setPage(batch.length > 0 ? 1 : 0)
          break
        }
        if (batch.length === 0) {
          setCanLoadMore(false)
          setReachedEnd(true)
          break
        }
        const unseen = batch.filter(profile => !listed.current.has(profile.username))
        nextPage += 1
        setPage(nextPage)
        if (unseen.length > 0) {
          unseen.forEach(profile => listed.current.add(profile.username))
          setProfiles(prev => [...prev, ...unseen])
          break
        }
        // A page of nothing but repeats: keep going so Load more isn't a no-op.
      }
    } catch {
      if (isCurrent()) setCanLoadMore(false)
    } finally {
      if (isCurrent()) setIsLoading(false)
    }
  }, [])

  // Deferred to a microtask so the fetch's setState calls don't run
  // synchronously inside the effect (React flags that as cascading renders).
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

      {profiles.length === 0 && !isLoading ? (
        <p className="muted">No profiles here yet.</p>
      ) : (
        <div className="user-list">
          {profiles.map((profile, index) => (
            <button
              key={profile.username}
              type="button"
              className="user-list__item"
              onClick={() => navigate(profilePathFor(profile.username))}
            >
              <span className="feed-post__rank" aria-label={`Rank ${index + 1}`}>
                #{index + 1}
              </span>
              <Avatar
                src={profile.author_profile_image_url}
                originalSrc={profile.author_profile_image_original_url}
                blurhash={profile.author_profile_image_blurhash}
                username={profile.username}
                size="sm"
              />
              <span className="user-list__name top-profile__name">{profile.username}</span>
              {profile.identity_is_verified && (
                <span className="verified-badge" aria-label="Verified">
                  ✓
                </span>
              )}
              <span className="top-profile__followers muted">{followerCountLabel(profile.follower_count)}</span>
            </button>
          ))}
        </div>
      )}

      {isLoading && <div className="center-spinner"><span className="spinner" /></div>}
      {canLoadMore && !isLoading && profiles.length > 0 && (
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
      {reachedEnd && !isLoading && profiles.length > 0 && (
        <FeedEndBanner message="That's the whole Top profiles board." />
      )}
    </div>
  )
}

export default TopProfilesList
