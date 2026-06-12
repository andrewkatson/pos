import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import HomePage from './HomePage'

vi.mock('../api/client', () => ({
  apiClient: {
    isAuthenticated: vi.fn(() => true),
    getPostsForUser: vi.fn().mockResolvedValue([]),
    searchUsers: vi.fn().mockResolvedValue([]),
    getFeed: vi.fn().mockResolvedValue([]),
    getFollowedFeed: vi.fn().mockResolvedValue([]),
    logout: vi.fn().mockResolvedValue({ message: 'ok' }),
    deleteAccount: vi.fn().mockResolvedValue({ message: 'ok' }),
    verifyIdentity: vi.fn().mockResolvedValue({ message: 'ok' }),
    setToken: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockIsAuthenticated = vi.mocked(apiClient.isAuthenticated)

function renderHome() {
  return render(
    <MemoryRouter initialEntries={['/home']}>
      <Routes>
        <Route path="/home" element={<HomePage />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockIsAuthenticated.mockReturnValue(true)
  vi.stubGlobal('localStorage', {
    getItem: vi.fn(() => 'ada'),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('renders the Home tab title and bottom navigation', () => {
  renderHome()
  expect(screen.getByRole('heading', { name: 'Your Posts' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Home/ })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Feed/ })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Post/ })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Settings/ })).toBeInTheDocument()
})

test('switches to the Feed tab', async () => {
  renderHome()
  await userEvent.click(screen.getByRole('button', { name: /Feed/ }))
  expect(screen.getByRole('heading', { name: 'Feed' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'For You' })).toBeInTheDocument()
})

test('switches to the Settings tab', async () => {
  renderHome()
  await userEvent.click(screen.getByRole('button', { name: /Settings/ }))
  expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Logout' })).toBeInTheDocument()
})

test('redirects to login when not authenticated', () => {
  mockIsAuthenticated.mockReturnValue(false)
  renderHome()
  expect(screen.getByText('Login page')).toBeInTheDocument()
})
