import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, test, expect } from 'vitest'
import ProfilePage from './ProfilePage'
import type { ProfileDetails } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: {
    isAuthenticated: vi.fn(() => true),
    getProfile: vi.fn(),
    getPostsForUser: vi.fn(),
    followUser: vi.fn(),
    unfollowUser: vi.fn(),
    toggleBlock: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockGetProfile = vi.mocked(apiClient.getProfile)
const mockGetPosts = vi.mocked(apiClient.getPostsForUser)
const mockFollow = vi.mocked(apiClient.followUser)
const mockUnfollow = vi.mocked(apiClient.unfollowUser)

const baseProfile: ProfileDetails = {
  username: 'bob',
  post_count: 2,
  follower_count: 10,
  following_count: 5,
  is_following: false,
  is_blocked: false,
  identity_is_verified: true,
  is_adult: true,
}

function renderProfile() {
  return render(
    <MemoryRouter initialEntries={['/profile/bob']}>
      <Routes>
        <Route path="/profile/:username" element={<ProfilePage />} />
        <Route path="/post/:postId" element={<div>Post page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockGetProfile.mockReset().mockResolvedValue(baseProfile)
  mockGetPosts.mockReset().mockResolvedValue([])
  mockFollow.mockReset().mockResolvedValue({ message: 'ok' })
  mockUnfollow.mockReset().mockResolvedValue({ message: 'ok' })
})

test('renders profile stats and follow button', async () => {
  renderProfile()
  expect(await screen.findByText('10')).toBeInTheDocument() // followers
  expect(screen.getByRole('button', { name: 'Follow' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Block' })).toBeInTheDocument()
})

test('following a user calls the API and updates the button', async () => {
  renderProfile()
  const followBtn = await screen.findByRole('button', { name: 'Follow' })
  await userEvent.click(followBtn)
  await waitFor(() => expect(mockFollow).toHaveBeenCalledWith('bob'))
  expect(screen.getByRole('button', { name: 'Following' })).toBeInTheDocument()
})

test('shows empty state when the user has no posts', async () => {
  renderProfile()
  expect(await screen.findByText("bob hasn't posted anything yet.")).toBeInTheDocument()
})

test('renders the post grid and opens a post', async () => {
  mockGetPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'bob', caption: 'hi' },
  ])
  renderProfile()
  await userEvent.click(await screen.findByRole('button', { name: 'Post by bob' }))
  expect(screen.getByText('Post page')).toBeInTheDocument()
})

test('shows "User not found" when the profile fails to load', async () => {
  mockGetProfile.mockRejectedValue(new Error('404'))
  renderProfile()
  expect(await screen.findByText('User not found.')).toBeInTheDocument()
})

test('redirects to login when unauthenticated', () => {
  vi.mocked(apiClient.isAuthenticated).mockReturnValueOnce(false)
  render(
    <MemoryRouter initialEntries={['/profile/bob']}>
      <Routes>
        <Route path="/profile/:username" element={<ProfilePage />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  )
  expect(screen.getByText('Login page')).toBeInTheDocument()
})
