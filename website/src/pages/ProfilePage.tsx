import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { apiClient } from '../api/client'
import { getCurrentUsername } from '../api/session'
import ProfileView from '../components/ProfileView'
import './MainApp.css'

/**
 * The /profile/:username route: a back bar wrapping the shared ProfileView.
 * This is where *other* people's profiles are shown — tapping your own name
 * anywhere goes to the Profile tab instead, via profilePathFor() (#347).
 *
 * The route still renders your own profile correctly (hiding Follow/Block) if
 * you reach it directly, e.g. from an old link or a pasted URL.
 *
 * This is also the page a shared profile link opens (issue #510), so it renders
 * for signed-out visitors too: they read the profile and its grid through the
 * public endpoints and see a prompt to log in instead of Follow / Block.
 *
 * The inner view is keyed by username so navigating between profiles fully
 * resets its state instead of briefly showing the previous user's data.
 */
function ProfilePage() {
  const { username = '' } = useParams<{ username: string }>()
  const navigate = useNavigate()
  // Read once per mount rather than per render: the session cannot change
  // underneath this page without a navigation, and a stable value keeps the
  // view's load effects from re-running.
  const [isSignedIn] = useState(() => apiClient.isAuthenticated())
  const currentUsername = isSignedIn ? getCurrentUsername() : null

  // A shared link opened cold has no history entry to pop, so Back would be a
  // dead control. Send those visitors somewhere real instead.
  function goBack() {
    if (window.history.length <= 1) navigate(isSignedIn ? '/home' : '/')
    else navigate(-1)
  }

  return (
    <div className="app-shell">
      <header className="app-bar">
        <button type="button" className="app-bar__back" onClick={goBack}>
          ← Back
        </button>
        <h1 className="app-bar__title">{username}</h1>
      </header>

      <main className="app-content">
        <ProfileView
          key={username}
          username={username}
          isOwnProfile={isSignedIn && currentUsername === username}
          currentUsername={currentUsername}
          isSignedIn={isSignedIn}
        />
      </main>
    </div>
  )
}

export default ProfilePage
