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
  const [hasMoreResults, setHasMoreResults] = useState(false)
  const [showAllResults, setShowAllResults] = useState(false)
  const [allSearchResults, setAllSearchResults] = useState<UserSearchResult[]>([])
  const [isLoadingAllResults, setIsLoadingAllResults] = useState(false)

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

        // If the first batch is full, check whether another result exists.
        if (results.length === 10) {
          const nextBatch = await apiClient.searchUsers(query, 1)

          if (!cancelled && isMounted.current) {
            setHasMoreResults(nextBatch.length > 0)
          }
        } else {
          setHasMoreResults(false)
        }
      } catch {
        if (!cancelled && isMounted.current) {
          setSearchResults([])
          setHasMoreResults(false)
        }
      }
    }, 500)

    return () => {
      cancelled = true
      clearTimeout(id)
    }
  }, [searchText])

  function handleSearchChange(value: string) {
    setSearchText(value)

    setShowAllResults(false)
    setAllSearchResults([])
    setHasMoreResults(false)

    if (value.trim().length < 3) {
      setSearchResults([])
    }
  }

  const isSearching = searchText.trim().length > 0

  async function openAllSearchResults() {
    const query = searchText.trim()

    if (query.length < 3) {
      return
    }

    setIsLoadingAllResults(true)

    try {
      const results: UserSearchResult[] = [...searchResults]
      let batch = 1

      while (true) {
        const nextBatch = await apiClient.searchUsers(query, batch)

        results.push(...nextBatch)

        if (nextBatch.length < 10) {
          break
        }

        batch += 1
      }

      if (isMounted.current && searchText.trim() === query) {
        setAllSearchResults(results)
        setShowAllResults(true)
      }
    } catch {
      // Keep the existing inline results visible if loading all results fails.
    } finally {
      if (isMounted.current) {
        setIsLoadingAllResults(false)
      }
    }
  }

  // Finding yourself in search should reveal the profile already behind this
  // tab, not navigate to /home — we're on /home, so that would look like a
  // dead tap. Clearing the query drops back to the profile body.
  function openSearchResult(resultUsername: string) {
    setShowAllResults(false)

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
              onClick={openAllSearchResults}
              disabled={isLoadingAllResults}
            >
              {isLoadingAllResults ? 'Loading...' : 'View all results'}
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
        <div
          className="search-results-dialog__backdrop"
          onClick={() => setShowAllResults(false)}
        >
          <div
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
                onClick={() => setShowAllResults(false)}
              >
                ×
              </button>
            </div>

            <div className="user-list">
              {allSearchResults.map(user => (
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
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ProfileTab