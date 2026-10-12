import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { apiClient } from '../api/client'
import { getCurrentUsername } from '../api/session'
import type { FeedPost, FollowCategory, TopPostPeriod } from '../api/types'
import { profilePathFor } from '../utils/profilePath'
import PostThumbnail from './PostThumbnail'
import PostActionBar from './PostActionBar'
import { usePostActions } from './usePostActions'
import Avatar from './Avatar'
import { captionFontClass } from './textFormatting'
import TopUsersBoard from './TopUsersBoard'

type FeedType = 'forYou' | 'following' | 'top'
/** 'all' is the whole following feed; the others narrow it by group (#392). */
type FeedGroup = 'all' | FollowCategory

const GROUP_OPTIONS: { value: FeedGroup; label: string }[] = [
  { value: 'all', label: 'Everyone' },
  // "Following" is the default bucket (not friend/family), matching the profile
  // relationship-category label; "Everyone" already covers the whole feed.
  { value: 'following', label: 'Following' },
  { value: 'friend', label: 'Friends' },
  { value: 'family', label: 'Family' },
]

const FEED_OPTIONS: { value: FeedType; label: string }[] = [
  { value: 'forYou', label: 'For You' },
  { value: 'following', label: 'Following' },
  { value: 'top', label: 'Top' },
]

/** What the Top feed ranks: posts by likes over a period (#558), or people by
 * followers right now (#562). */
type TopKind = 'posts' | 'people'

const TOP_KIND_OPTIONS: { value: TopKind; label: string }[] = [
  { value: 'posts', label: 'Posts' },
  { value: 'people', label: 'People' },
]

const PERIOD_OPTIONS: { value: TopPostPeriod; label: string }[] = [
  { value: 'day', label: 'Today' },
  { value: 'week', label: 'This week' },
  { value: 'month', label: 'This month' },
  { value: 'year', label: 'This year' },
]

/**
 * The "Feed" tab with a For You / Following / Top segmented control. Each feed
 * loads independently and supports pagination. Top is the scoreboard of the
 * most-liked public posts across the app over a chosen period (issue #558). Mirrors iOS FeedView (ForYou +
 * Following feeds, infinite scroll, tap author → profile, tap image → detail).
 *
 * Each post carries the same like / report / delete controls as the profile
 * grid, so the feed can be acted on without opening each post (issue #267).
 */
function FeedTab() {
  const navigate = useNavigate()
  const [selected, setSelected] = useState<FeedType>('forYou')
  const [group, setGroup] = useState<FeedGroup>('all')
  const [period, setPeriod] = useState<TopPostPeriod>('week')
  const [topKind, setTopKind] = useState<TopKind>('posts')
  // The People board loads its own list; the post list stays idle under it.
  const showPeopleBoard = selected === 'top' && topKind === 'people'

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
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const { stateFor, toggleLike, toggleSave, openMenu, openMenuPostId, openLikes, dialogs } =
    usePostActions({
      currentUsername: getCurrentUsername(),
      // Deleting from the feed drops the row rather than reloading the whole
      // feed, which would reshuffle the weighted ordering under the user (#267).
      onPostDeleted: postIdentifier =>
        setPosts(prev => prev.filter(post => post.post_identifier !== postIdentifier)),
      onError: setErrorMessage,
    })

  const fetcher = useCallback(
    (batch: number) => {
      if (selected === 'forYou') return apiClient.getFeed(batch)
      if (selected === 'top') {
        return topKind === 'people' ? Promise.resolve([]) : apiClient.getTopPosts(batch, period)
      }
      return apiClient.getFollowedFeed(batch, group === 'all' ? undefined : group)
    },
    [selected, group, period, topKind],
  )

  // Bumped on every from-scratch load. A response from an older generation —
  // say a Week page still in flight after the user picked Year, or a For You
  // page after switching to Top — is dropped instead of overwriting or being
  // appended to the newer feed.
  const loadGeneration = useRef(0)
  // Ids already in the list, kept in step with `posts` so a page load can tell
  // synchronously whether a page added anything new.
  const listedIds = useRef(new Set<string>())

  const loadFeed = useCallback(
    async (pageToLoad: number, replace: boolean) => {
      if (replace) loadGeneration.current += 1
      const generation = loadGeneration.current
      const isCurrent = () => isMounted.current && generation === loadGeneration.current
      try {
        let nextPage = pageToLoad
        for (;;) {
          const newPosts = await fetcher(nextPage)
          if (!isCurrent()) return
          if (replace) {
            listedIds.current = new Set(newPosts.map(post => post.post_identifier))
            setPosts(newPosts)
            setCanLoadMore(newPosts.length > 0)
            setPage(newPosts.length > 0 ? 1 : 0)
            break
          }
          if (newPosts.length === 0) {
            setCanLoadMore(false)
            break
          }
          // Live OFFSET paging can repeat a post whose rank moved between
          // requests (Top especially); drop repeats so keys stay unique.
          const unseen = newPosts.filter(post => !listedIds.current.has(post.post_identifier))
          nextPage += 1
          setPage(nextPage)
          if (unseen.length > 0) {
            unseen.forEach(post => listedIds.current.add(post.post_identifier))
            setPosts(prev => [...prev, ...unseen])
            break
          }
          // A page of nothing but repeats would make "Load more" look like it
          // did nothing; keep going until a page adds something or comes back
          // empty (the server stops the Top board at 100).
        }
      } catch {
        if (isCurrent()) setCanLoadMore(false)
      } finally {
        // A superseded load leaves the spinner to the load that replaced it.
        if (isCurrent()) setIsLoading(false)
      }
    },
    [fetcher],
  )

  // Switching feed, group or period clears the list up front, so the previous
  // selection's posts never sit under the new one — ranked as if they were
  // the new Top board — while it loads, or for good if that load fails.
  function startSelectionChange() {
    // Invalidate in-flight loads now, not when the reload starts: that waits
    // for a render and a microtask, and an old response landing in between
    // would otherwise repopulate the list just cleared below.
    loadGeneration.current += 1
    listedIds.current = new Set()
    setIsLoading(true)
    setPosts([])
    setCanLoadMore(true)
  }

  // Reload from scratch whenever the selected feed changes. Deferred to a
  // microtask so the fetch's setState calls don't run synchronously inside the
  // effect (React flags that as cascading renders).
  useEffect(() => {
    void Promise.resolve().then(() => loadFeed(0, true))
  }, [loadFeed])

  return (
    <div>
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

      <div className="segmented" role="tablist" aria-label="Feed type">
        {FEED_OPTIONS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={selected === value}
            className={`segmented__option${selected === value ? ' segmented__option--active' : ''}`}
            onClick={() => {
              // Re-selecting the current feed wouldn't change `selected`, so
              // the reload effect wouldn't fire — guard against a stuck spinner.
              if (value === selected) return
              startSelectionChange()
              setSelected(value)
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {selected === 'following' && (
        <label className="feed-group-filter">
          <span className="visually-hidden">Filter by group</span>
          <select
            className="select-input"
            aria-label="Filter following feed by group"
            value={group}
            onChange={e => {
              const next = e.target.value as FeedGroup
              // Re-selecting the current group wouldn't change `group`, so the
              // reload effect wouldn't fire — guard against a stuck spinner.
              if (next === group) return
              startSelectionChange()
              setGroup(next)
            }}
          >
            {GROUP_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      )}

      {selected === 'top' && (
        <div className="segmented" role="tablist" aria-label="Top board">
          {TOP_KIND_OPTIONS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={topKind === value}
              className={`segmented__option${topKind === value ? ' segmented__option--active' : ''}`}
              onClick={() => {
                if (value === topKind) return
                startSelectionChange()
                setTopKind(value)
              }}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {showPeopleBoard ? (
        <TopUsersBoard />
      ) : (
        <>
        {selected === 'top' && (
          <label className="feed-group-filter">
            <span className="visually-hidden">Time period</span>
            <select
              className="select-input"
              aria-label="Top posts time period"
              value={period}
              onChange={e => {
                const next = e.target.value as TopPostPeriod
                if (next === period) return
                startSelectionChange()
                setPeriod(next)
              }}
            >
              {PERIOD_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
        )}

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
            {posts.map((post, index) => (
              <article key={post.post_identifier}>
                <div className="author-line">
                  {/* The scoreboard position (issue #558). Deleting a row from
                      Top shifts the ranks below it up, matching a refresh. */}
                  {selected === 'top' && (
                    <span className="feed-post__rank" aria-label={`Rank ${index + 1}`}>
                      #{index + 1}
                    </span>
                  )}
                  <Avatar
                    src={post.author_profile_image_url}
                    originalSrc={post.author_profile_image_original_url}
                    blurhash={post.author_profile_image_blurhash}
                    username={post.author_username}
                    size="sm"
                  />
                  <button
                    type="button"
                    className="feed-post__author"
                    onClick={() => navigate(profilePathFor(post.author_username))}
                  >
                    {post.author_username}
                  </button>
                </div>
                <button
                  type="button"
                  className="feed-post__image"
                  aria-label={`Open post by ${post.author_username}`}
                  onClick={() => navigate(`/post/${post.post_identifier}`)}
                >
                  <PostThumbnail post={post} />
                </button>
                {/* The caption under the photo (issue #378). Text-only posts (#307)
                    already render their caption as the tile above, so it isn't
                    repeated for them. The author's chosen caption font (issue
                    #318) applies here too, so the feed matches the detail view
                    (issue #450). */}
                {post.image_url !== null && (
                  <p className={`feed-post__caption ${captionFontClass(post.caption_font)}`.trim()}>
                    {post.caption}
                  </p>
                )}
                {/* Comment count and post time only appear here: feed rows have
                    the width for them, the square profile tiles don't (#249). */}
                <PostActionBar
                  post={post}
                  state={stateFor(post)}
                  onToggleLike={toggleLike}
                  onToggleSave={toggleSave}
                  onOpenMenu={openMenu}
                  isMenuOpen={openMenuPostId === post.post_identifier}
                  onOpenLikes={openLikes}
                  onOpenPost={p => navigate(`/post/${p.post_identifier}`)}
                  showDetails
                />
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

        </>
      )}

      {dialogs}
    </div>
  )
}

export default FeedTab
