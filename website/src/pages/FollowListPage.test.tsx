import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, test, expect } from 'vitest'
import FollowListPage from './FollowListPage'
import type { UserSearchResult } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: {
    isAuthenticated: vi.fn(() => true),
    getFollowers: vi.fn(),
    getFollowing: vi.fn(),
  },
}))

// The Profile tab is reached via '/home'; profilePathFor sends your own name
// there, so stub the current username to keep rows pointing at other people.
vi.mock('../api/session', () => ({
  getCurrentUsername: vi.fn(() => 'viewer'),
}))

import { apiClient } from '../api/client'
const mockIsAuthenticated = vi.mocked(apiClient.isAuthenticated)
const mockGetFollowers = vi.mocked(apiClient.getFollowers)
const mockGetFollowing = vi.mocked(apiClient.getFollowing)

const users: UserSearchResult[] = [
  { username: 'alice', identity_is_verified: true },
  { username: 'bob', identity_is_verified: false },
]

function renderPage(mode: 'followers' | 'following') {
  const path = `/${mode}`
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/followers" element={<FollowListPage mode="followers" />} />
        <Route path="/following" element={<FollowListPage mode="following" />} />
        <Route path="/profile/:username" element={<div>Profile page</div>} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockIsAuthenticated.mockReset().mockReturnValue(true)
  mockGetFollowers.mockReset().mockResolvedValue([])
  mockGetFollowing.mockReset().mockResolvedValue([])
})

test('redirects to login when not authenticated', async () => {
  mockIsAuthenticated.mockReturnValue(false)
  renderPage('followers')
  expect(await screen.findByText('Login page')).toBeInTheDocument()
  expect(mockGetFollowers).not.toHaveBeenCalled()
})

test('followers mode loads followers and titles the page', async () => {
  mockGetFollowers.mockResolvedValue(users)
  renderPage('followers')

  expect(await screen.findByText('alice')).toBeInTheDocument()
  expect(screen.getByText('bob')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Followers' })).toBeInTheDocument()
  expect(mockGetFollowers).toHaveBeenCalled()
  expect(mockGetFollowing).not.toHaveBeenCalled()
  // Only alice is identity-verified.
  expect(screen.getAllByLabelText('Verified')).toHaveLength(1)
})

test('following mode loads following and titles the page', async () => {
  mockGetFollowing.mockResolvedValue(users)
  renderPage('following')

  expect(await screen.findByText('alice')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Following' })).toBeInTheDocument()
  expect(mockGetFollowing).toHaveBeenCalled()
  expect(mockGetFollowers).not.toHaveBeenCalled()
})

test('tapping a user navigates to their profile', async () => {
  mockGetFollowers.mockResolvedValue(users)
  const user = userEvent.setup()
  renderPage('followers')

  await user.click(await screen.findByRole('button', { name: /alice/ }))
  expect(await screen.findByText('Profile page')).toBeInTheDocument()
})

test('shows an empty state for followers', async () => {
  renderPage('followers')
  expect(await screen.findByText("You don't have any followers yet.")).toBeInTheDocument()
})

test('shows an empty state for following', async () => {
  renderPage('following')
  expect(await screen.findByText("You aren't following anyone yet.")).toBeInTheDocument()
})

test('surfaces a load error', async () => {
  mockGetFollowers.mockRejectedValue(new Error('Failed to load.'))
  renderPage('followers')
  expect(await screen.findByText('Failed to load.')).toBeInTheDocument()
})
