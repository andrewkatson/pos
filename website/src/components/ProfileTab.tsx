import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { apiClient } from '../api/client'
import { getCurrentUsername } from '../api/session'
import type { UserSearchResult } from '../api/types'
import { profilePathFor } from '../utils/profilePath'
import ProfileView from './ProfileView'
import Avatar from './Avatar'

/**
 * The "Profile" tab: the signed-in user's own profile — stats and their post
 * grid — reachable straight from the bottom bar (issue #347). It replaces the
 * old "Home" tab, which showed the same grid without the profile stats.
 *
 * The user-search bar lives here (as it did on Home) and swaps the profile for
 * a results list while a query is active. Mirrors iOS MyPostsGridView +
 * HomeViewModel (debounced search, 3-char minimum).
 */
function ProfileTab() {
  const navigate = useNavigate()
  const username = getCurrentUsername()

  // Track mount state so a search that resolves after the tab is switched away
  // (HomePage unmounts inactive tabs) doesn't set state on an unmounted view.
  const isMounted = useRef(true)
  useEffect(() => {
    isMounted.current = true
    return () => {
      isMounted.current = false
    }
  }, [])

  const [searchText, setSearchText] = useState('')
  const [searchResults, setSearchResults] = useState<UserSearchResult[]>([])
  // Results beyond the first batch, shown only in the "all results" dialog.
  // The debounced search already fetches batch 1 to decide whether to offer
  // "View all results", so that batch is kept rather than requested again.
  const [moreResults, setMoreResults] = useState<UserSearchResult[]>([])
  // Whether the last batch fetched was full, i.e. another may exist. The
  // endpoint is rate-limited (30/min), so the dialog pages one batch per
  // "Load more" press instead of fetching every batch up front.
  const [canLoadMore, setCanLoadMore] = useState(false)
  const [nextBatch, setNextBatch] = useState(2)
  const [showAllResults, setShowAllResults] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [loadMoreFailed, setLoadMoreFailed] = useState(false)

  // Bumped whenever the query changes so a "Load more" response for an old
  // query is dropped instead of being spliced into the new query's results.
  const searchGeneration = useRef(0)

  const hasMoreResults = moreResults.length > 0

  // Debounced user search (500ms), only firing for 3+ character queries. The
  // setState lives in the timeout callback (not synchronously in the effect);
  // clearing for short queries is handled in the input's onChange below.
  useEffect(() => {
    const query = searchText.trim()

    if (query.length < 3) {
      return
    }

    let cancelled = false

    const id = setTimeout(async () => {
      try {
        const results = await apiClient.searchUsers(query, 0)

        if (cancelled || !isMounted.current) {
          return
        }

        setSearchResults(results)

        // If the first batch is full, fetch the second to learn whether more
        // results exist; it doubles as the first page of the dialog.
        if (results.length === 10) {
          try {
            const secondBatch = await apiClient.searchUsers(query, 1)

            if (!cancelled && isMounted.current) {
              setMoreResults(secondBatch)
              setCanLoadMore(secondBatch.length === 10)
              setNextBatch(2)
            }
          } catch {
            // Keep the successful first batch visible if the optional
            // check for additional results fails.
            if (!cancelled && isMounted.current) {
              setMoreResults([])
              setCanLoadMore(false)
            }
          }
        } else {
          setMoreResults([])
          setCanLoadMore(false)
        }
      } catch {
        if (!cancelled && isMounted.current) {
          setSearchResults([])
          setMoreResults([])
          setCanLoadMore(false)
        }
      }
    }, 500)

    return () => {
      cancelled = true
      clearTimeout(id)
    }
  }, [searchText])

  function handleSearchChange(value: string) {
    searchGeneration.current += 1
    setSearchText(value)

    closeAllResults()
    setMoreResults([])
    setCanLoadMore(false)
    setIsLoadingMore(false)
    setLoadMoreFailed(false)

    if (value.trim().length < 3) {
      setSearchResults([])
    }
  }

  const isSearching = searchText.trim().length > 0

  // Focus lifecycle for the results dialog: remember what opened it so focus
  // can go back there on close (the "View all results" button, normally).
  const dialogRef = useRef<HTMLDivElement>(null)
  const dialogOpenerRef = useRef<HTMLElement | null>(null)

  function openAllResults() {
    dialogOpenerRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    setShowAllResults(true)
  }

  function closeAllResults() {
    setShowAllResults(false)

    const opener = dialogOpenerRef.current
    dialogOpenerRef.current = null
    // The opener may already be gone (e.g. the query was cleared), in which
    // case there is nothing sensible to hand focus back to.
    if (opener?.isConnected) {
      opener.focus()
    }
  }

  // While the dialog is open: move focus into it, close on Escape, and keep
  // Tab cycling inside it so a keyboard user can't land on the page behind
  // the backdrop — what `aria-modal` promises assistive tech.
  useEffect(() => {
    if (!showAllResults) {
      return
    }

    const dialog = dialogRef.current
    focusableIn(dialog)[0]?.focus()

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeAllResults()
        return
      }

      if (event.key !== 'Tab' || !dialog) {
        return
      }

      const focusable = focusableIn(dialog)
      if (focusable.length === 0) {
        event.preventDefault()
        return
      }

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement

      if (event.shiftKey && (active === first || !dialog.contains(active))) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && (active === last || !dialog.contains(active))) {
        event.preventDefault()
        first.focus()
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [showAllResults])

  async function loadMoreResults() {
    const query = searchText.trim()

    if (query.length < 3 || isLoadingMore || !canLoadMore) {
      return
    }

    const generation = searchGeneration.current
    const batch = nextBatch

    setIsLoadingMore(true)
    setLoadMoreFailed(false)

    try {
      const results = await apiClient.searchUsers(query, batch)

      if (!isMounted.current || generation !== searchGeneration.current) {
        return
      }

      setMoreResults(previous => [...previous, ...results])
      setCanLoadMore(results.length === 10)
      setNextBatch(batch + 1)
    } catch {
      if (isMounted.current && generation === searchGeneration.current) {
        setLoadMoreFailed(true)
      }
    } finally {
      if (isMounted.current && generation === searchGeneration.current) {
        setIsLoadingMore(false)
      }
    }
  }

  // Finding yourself in search should reveal the profile already behind this
  // tab, not navigate to /home — we're on /home, so that would look like a
  // dead tap. Clearing the query drops back to the profile body.
  function openSearchResult(resultUsername: string) {
    closeAllResults()

    if (resultUsername === username) {
      handleSearchChange('')
      return
    }

    navigate(profilePathFor(resultUsername))
  }

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
              onClick={() => openSearchResult(user.username)}
            >
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
            </button>
          ))}

          {hasMoreResults && (
            <button
              type="button"
              className="search-results__view-all"
              onClick={openAllResults}
            >
              View all results
            </button>
          )}

          {searchText.trim().length >= 3 && searchResults.length === 0 && (
            <p className="muted">No users found.</p>
          )}
        </div>
      ) : username ? (
        <ProfileView username={username} isOwnProfile currentUsername={username} />
      ) : (
        // No session username cached (the shell already bounces to login); render
        // a message rather than requesting a profile for an empty username.
        <p className="muted">Sign in to see your profile.</p>
      )}

      {showAllResults && (
        <div className="search-results-dialog__backdrop" onClick={closeAllResults}>
          <div
            ref={dialogRef}
            className="search-results-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="search-results-dialog-title"
            onClick={event => event.stopPropagation()}
          >
            <div className="search-results-dialog__header">
              <h2 id="search-results-dialog-title">Search results</h2>

              <button
                type="button"
                aria-label="Close search results"
                onClick={closeAllResults}
              >
                ×
              </button>
            </div>

            <div className="user-list">
              {[...searchResults, ...moreResults].map(user => (
                <button
                  key={user.username}
                  type="button"
                  className="user-list__item"
                  onClick={() => openSearchResult(user.username)}
                >
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
                </button>
              ))}

              {loadMoreFailed && (
                <p className="muted" role="alert">
                  Couldn't load more results. Try again.
                </p>
              )}

              {canLoadMore && (
                <button
                  type="button"
                  className="search-results__view-all"
                  onClick={loadMoreResults}
                  disabled={isLoadingMore}
                >
                  {isLoadingMore ? 'Loading...' : 'Load more'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/** Tabbable descendants of `root`, in DOM order. */
function focusableIn(root: HTMLElement | null): HTMLElement[] {
  if (!root) {
    return []
  }

  return Array.from(
    root.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  )
}

export default ProfileTab
