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
    likePost: vi.fn(),
    unlikePost: vi.fn(),
    reportPost: vi.fn(),
    retractReportPost: vi.fn(),
    deletePost: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockGetProfile = vi.mocked(apiClient.getProfile)
const mockGetPosts = vi.mocked(apiClient.getPostsForUser)
const mockFollow = vi.mocked(apiClient.followUser)
const mockUnfollow = vi.mocked(apiClient.unfollowUser)
const mockLikePost = vi.mocked(apiClient.likePost)
const mockUnlikePost = vi.mocked(apiClient.unlikePost)
const mockReportPost = vi.mocked(apiClient.reportPost)
const mockRetractReport = vi.mocked(apiClient.retractReportPost)

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
  mockLikePost.mockReset().mockResolvedValue({ message: 'ok' })
  mockUnlikePost.mockReset().mockResolvedValue({ message: 'ok' })
  mockReportPost.mockReset().mockResolvedValue({ message: 'ok' })
  mockRetractReport.mockReset().mockResolvedValue({ message: 'ok' })
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

test('refresh reloads both the profile details and the posts', async () => {
  mockGetPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'bob', caption: 'hi' },
  ])
  renderProfile()
  await screen.findByRole('button', { name: 'Post by bob' })
  expect(mockGetPosts).toHaveBeenCalledTimes(1)
  expect(mockGetProfile).toHaveBeenCalledTimes(1)

  await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
  // Both the posts and the profile details (follow/block/counts) reload, so the
  // follow state can't go stale on refresh.
  await waitFor(() => expect(mockGetPosts).toHaveBeenCalledTimes(2))
  await waitFor(() => expect(mockGetProfile).toHaveBeenCalledTimes(2))
  expect(mockGetPosts).toHaveBeenLastCalledWith('bob', 0)
  expect(mockGetProfile).toHaveBeenLastCalledWith('bob')
})

test('offers a retry when the profile fails to load', async () => {
  // A missing user and a transient network error are indistinguishable here, so
  // the view offers a way out rather than a dead end.
  mockGetProfile.mockRejectedValueOnce(new Error('boom'))
  renderProfile()

  expect(await screen.findByText("Couldn't load bob's profile.")).toBeInTheDocument()

  // Retrying succeeds and the profile renders.
  mockGetProfile.mockResolvedValue(baseProfile)
  await userEvent.click(screen.getByRole('button', { name: 'Try again' }))

  expect(await screen.findByText('10')).toBeInTheDocument()
  expect(screen.queryByText("Couldn't load bob's profile.")).not.toBeInTheDocument()
})

// ---- In-place post actions on the grid (issue #267) ----

test('likes a post straight from the grid and reflects the new count', async () => {
  mockGetPosts.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'bob',
      caption: 'hi',
      post_likes: 3,
      is_liked: false,
    },
  ])
  renderProfile()

  const like = await screen.findByRole('button', { name: 'Like post' })
  expect(screen.getByText('3')).toBeInTheDocument()
  await userEvent.click(like)

  await waitFor(() => expect(mockLikePost).toHaveBeenCalledWith('p1'))
  // Optimistic: the control flips and the count climbs without a refetch.
  expect(await screen.findByRole('button', { name: 'Unlike post' })).toBeInTheDocument()
  expect(screen.getByText('4')).toBeInTheDocument()
})

test('reverts the like when the request fails', async () => {
  mockGetPosts.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'bob',
      caption: 'hi',
      post_likes: 3,
      is_liked: false,
    },
  ])
  mockLikePost.mockRejectedValue(new Error('nope'))
  renderProfile()

  await userEvent.click(await screen.findByRole('button', { name: 'Like post' }))

  // Back to the pre-click state, with the failure surfaced.
  expect(await screen.findByRole('alert')).toHaveTextContent('nope')
  expect(screen.getByRole('button', { name: 'Like post' })).toBeInTheDocument()
  expect(screen.getByText('3')).toBeInTheDocument()
})

test('reports a post from the grid', async () => {
  mockGetPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'bob', caption: 'hi' },
  ])
  renderProfile()

  await userEvent.click(await screen.findByRole('button', { name: 'Options for post by bob' }))
  await userEvent.click(screen.getByRole('button', { name: 'Report' }))
  await userEvent.type(screen.getByLabelText('Reason for reporting'), 'mean')
  await userEvent.click(screen.getByRole('button', { name: 'Submit Report' }))

  await waitFor(() => expect(mockReportPost).toHaveBeenCalledWith('p1', 'mean'))
  // The row now shows the reported flag.
  expect(await screen.findByLabelText('You reported this post')).toBeInTheDocument()
})

test('offers retract report when the post is already reported', async () => {
  // The listing endpoint carries is_reported/report_reason, so the grid knows
  // to offer retraction without opening the post first (issues #267, #176).
  mockGetPosts.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'bob',
      caption: 'hi',
      is_reported: true,
      report_reason: 'was mean',
    },
  ])
  renderProfile()

  await userEvent.click(await screen.findByRole('button', { name: 'Options for post by bob' }))
  await userEvent.click(screen.getByRole('button', { name: 'Retract Report' }))
  // The original reason is shown back to the user before they confirm.
  expect(screen.getByLabelText('Your report reason')).toHaveValue('was mean')
  await userEvent.click(screen.getByRole('button', { name: 'Retract Report' }))

  await waitFor(() => expect(mockRetractReport).toHaveBeenCalledWith('p1'))
  await waitFor(() =>
    expect(screen.queryByLabelText('You reported this post')).not.toBeInTheDocument(),
  )
})

test('does not offer delete on another user post', async () => {
  mockGetPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'bob', caption: 'hi' },
  ])
  renderProfile()

  await userEvent.click(await screen.findByRole('button', { name: 'Options for post by bob' }))
  expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
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
