import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import ProfileTab from '../components/ProfileTab'
import FeedTab from '../components/FeedTab'
import NewPostTab from '../components/NewPostTab'
import SettingsTab from '../components/SettingsTab'
import { apiClient } from '../api/client'
import './MainApp.css'

type Tab = 'profile' | 'feed' | 'post' | 'settings'

const TAB_TITLES: Record<Tab, string> = {
  profile: 'Your Profile',
  feed: 'Feed',
  post: 'Create Post',
  settings: 'Settings',
}

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'profile', label: 'Profile', icon: '👤' },
  { id: 'feed', label: 'Feed', icon: '📰' },
  { id: 'post', label: 'Post', icon: '➕' },
  { id: 'settings', label: 'Settings', icon: '⚙️' },
]

function isTab(value: string | null): value is Tab {
  return TABS.some(({ id }) => id === value)
}

/**
 * The signed-in app shell: a bottom tab bar switching between your own Profile,
 * the Feed, New Post creation, and Settings. Mirrors the iOS HomeView TabView.
 *
 * The first tab was formerly "Home" (the same post grid without the profile
 * stats); it became "Profile" so your own profile is one tap away (issue #347).
 *
 * The selected tab lives in the URL (`?tab=feed`, with Profile as the bare
 * `/home` default) rather than in local state, so navigation can actually
 * reach it: tapping your own username routes to `/home`, and that has to
 * select the Profile tab even when you are already on `/home` with another tab
 * showing — which local state could not do, since the pathname wouldn't change.
 */
function HomePage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const tabParam = searchParams.get('tab')
  const tab: Tab = isTab(tabParam) ? tabParam : 'profile'

  function selectTab(next: Tab) {
    // Profile is the default, so it stays as a bare /home — which is what
    // profilePathFor() navigates to. Replace rather than push so the tab bar
    // doesn't fill the back stack.
    setSearchParams(next === 'profile' ? {} : { tab: next }, { replace: true })
  }

  // Guard the authenticated surface: bounce to login if there's no session.
  useEffect(() => {
    if (!apiClient.isAuthenticated()) {
      navigate('/login', { replace: true })
    }
  }, [navigate])

  return (
    <div className="app-shell">
      <header className="app-bar">
        <h1 className="app-bar__title">{TAB_TITLES[tab]}</h1>
      </header>

      <main className="app-content">
        {tab === 'profile' && <ProfileTab />}
        {tab === 'feed' && <FeedTab />}
        {tab === 'post' && <NewPostTab onPosted={() => selectTab('profile')} />}
        {tab === 'settings' && <SettingsTab />}
      </main>

      <nav className="tab-bar" aria-label="Main navigation">
        {TABS.map(({ id, label, icon }) => (
          <button
            key={id}
            type="button"
            className={`tab-bar__item${tab === id ? ' tab-bar__item--active' : ''}`}
            aria-current={tab === id ? 'page' : undefined}
            onClick={() => selectTab(id)}
          >
            <span className="tab-bar__icon" aria-hidden="true">
              {icon}
            </span>
            {label}
          </button>
        ))}
      </nav>
    </div>
  )
}

export default HomePage
