import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import { getCurrentUsername } from '../api/session'
import type { UserSearchResult } from '../api/types'
import { profilePathFor } from '../utils/profilePath'
import ProfileView from './ProfileView'

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

  // Finding yourself in search should reveal the profile already behind this
  // tab, not navigate to /home — we're on /home, so that would look like a
  // dead tap. Clearing the query drops back to the profile body.
  function openSearchResult(resultUsername: string) {
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
      ) : username ? (
        <ProfileView username={username} isOwnProfile currentUsername={username} />
      ) : (
        // No session username cached (the shell already bounces to login); render
        // a message rather than requesting a profile for an empty username.
        <p className="muted">Sign in to see your profile.</p>
      )}
    </div>
  )
}

export default ProfileTab
