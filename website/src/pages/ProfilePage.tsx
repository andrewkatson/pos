import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { apiClient } from '../api/client'
import { getCurrentUsername } from '../api/session'
import ProfileView from '../components/ProfileView'
import './MainApp.css'

/**
 * The /profile/:username route: a back bar wrapping the shared ProfileView.
 * Your own profile is normally reached from the Profile tab instead (#347), but
 * this route still renders it — e.g. when tapping your own name on a post.
 *
 * The inner view is keyed by username so navigating between profiles fully
 * resets its state instead of briefly showing the previous user's data.
 */
function ProfilePage() {
  const { username = '' } = useParams<{ username: string }>()
  const navigate = useNavigate()
  // This view hits authenticated endpoints, so require a session like HomePage.
  if (!apiClient.isAuthenticated()) {
    return <Navigate to="/login" replace />
  }

  const currentUsername = getCurrentUsername()

  return (
    <div className="app-shell">
      <header className="app-bar">
        <button type="button" className="app-bar__back" onClick={() => navigate(-1)}>
          ← Back
        </button>
        <h1 className="app-bar__title">{username}</h1>
      </header>

      <main className="app-content">
        <ProfileView
          key={username}
          username={username}
          isOwnProfile={currentUsername === username}
          currentUsername={currentUsername}
        />
      </main>
    </div>
  )
}

export default ProfilePage
