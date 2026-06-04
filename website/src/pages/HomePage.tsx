import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import MyPostsTab from '../components/MyPostsTab'
import FeedTab from '../components/FeedTab'
import NewPostTab from '../components/NewPostTab'
import SettingsTab from '../components/SettingsTab'
import { apiClient } from '../api/client'
import './MainApp.css'

type Tab = 'home' | 'feed' | 'post' | 'settings'

const TAB_TITLES: Record<Tab, string> = {
  home: 'Your Posts',
  feed: 'Feed',
  post: 'Create Post',
  settings: 'Settings',
}

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'home', label: 'Home', icon: '🏠' },
  { id: 'feed', label: 'Feed', icon: '📰' },
  { id: 'post', label: 'Post', icon: '➕' },
  { id: 'settings', label: 'Settings', icon: '⚙️' },
]

/**
 * The signed-in app shell: a bottom tab bar switching between the My Posts grid,
 * the Feed, New Post creation, and Settings. Mirrors the iOS HomeView TabView.
 */
function HomePage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('home')

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
        {tab === 'home' && <MyPostsTab />}
        {tab === 'feed' && <FeedTab />}
        {tab === 'post' && <NewPostTab onPosted={() => setTab('home')} />}
        {tab === 'settings' && <SettingsTab />}
      </main>

      <nav className="tab-bar" aria-label="Main navigation">
        {TABS.map(({ id, label, icon }) => (
          <button
            key={id}
            type="button"
            className={`tab-bar__item${tab === id ? ' tab-bar__item--active' : ''}`}
            aria-current={tab === id ? 'page' : undefined}
            onClick={() => setTab(id)}
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
