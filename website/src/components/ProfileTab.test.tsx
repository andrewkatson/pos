import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import ProfileTab from './ProfileTab'

vi.mock('../api/client', () => ({
  apiClient: {
    getPostsForUser: vi.fn(),
    getProfile: vi.fn(),
    searchUsers: vi.fn(),
    likePost: vi.fn(),
    unlikePost: vi.fn(),
    reportPost: vi.fn(),
    retractReportPost: vi.fn(),
    deletePost: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockGetPosts = vi.mocked(apiClient.getPostsForUser)
const mockGetProfile = vi.mocked(apiClient.getProfile)
const mockSearch = vi.mocked(apiClient.searchUsers)
const mockDeletePost = vi.mocked(apiClient.deletePost)

const profile = {
  username: 'ada',
  post_count: 4,
  follower_count: 12,
  following_count: 7,
  is_following: false,
  is_blocked: false,
  identity_is_verified: false,
  is_adult: true,
}

function renderTab() {
  return render(
    <MemoryRouter initialEntries={['/home']}>
      <Routes>
        <Route path="/home" element={<ProfileTab />} />
        <Route path="/post/:postId" element={<div>Post page</div>} />
        <Route path="/profile/:username" element={<div>Profile page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockGetPosts.mockReset()
  mockGetProfile.mockReset()
  mockSearch.mockReset()
  mockDeletePost.mockReset()
  mockGetProfile.mockResolvedValue(profile)
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

test('shows the signed-in user own profile stats', async () => {
  mockGetPosts.mockResolvedValue([])
  renderTab()

  // The stats are what the tab adds over the post grid it replaced (#347).
  expect(await screen.findByText('12')).toBeInTheDocument()
  expect(screen.getByText('Followers')).toBeInTheDocument()
  expect(screen.getByText('7')).toBeInTheDocument()
  expect(screen.getByText('Following')).toBeInTheDocument()
  expect(mockGetProfile).toHaveBeenCalledWith('ada')
})

test('does not offer follow or block on your own profile', async () => {
  mockGetPosts.mockResolvedValue([])
  renderTab()
  await screen.findByText('Followers')
  expect(screen.queryByRole('button', { name: 'Follow' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Block' })).not.toBeInTheDocument()
})

test('renders the current user post grid and opens a post', async () => {
  mockGetPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
  ])
  renderTab()
  const cell = await screen.findByRole('button', { name: 'Post by ada' })
  await userEvent.click(cell)
  expect(screen.getByText('Post page')).toBeInTheDocument()
})

test('falls back to the original image when the compressed one fails to load', async () => {
  // The compressed copy is produced by an async Lambda, so a just-posted (or
  // recently hidden) image can 404 in the compressed bucket for a while. The
  // grid should fall back to the full-resolution original rather than showing a
  // broken image (issues #252/#254).
  mockGetPosts.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://compressed/1.jpg',
      original_image_url: 'http://original/1.jpg',
      author_username: 'ada',
      caption: 'hi',
    },
  ])
  renderTab()
  const img = (await screen.findByAltText('hi')) as HTMLImageElement
  expect(img.getAttribute('src')).toBe('http://compressed/1.jpg')

  // Simulate the compressed image failing to load.
  fireEvent.error(img)
  expect(img.getAttribute('src')).toBe('http://original/1.jpg')

  // A second failure (e.g. the original also 404s) must not loop back.
  fireEvent.error(img)
  expect(img.getAttribute('src')).toBe('http://original/1.jpg')
})

test('shows empty state when the user has no posts', async () => {
  mockGetPosts.mockResolvedValue([])
  renderTab()
  expect(await screen.findByText("You haven't posted anything yet.")).toBeInTheDocument()
})

test('deleting your own post from the grid removes it and drops the count', async () => {
  // Issue #267: you can delete from the grid without opening the post.
  mockGetPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
  ])
  mockDeletePost.mockResolvedValue({ message: 'ok' })
  renderTab()

  await userEvent.click(await screen.findByRole('button', { name: 'Options for post by ada' }))
  // Your own post offers Delete rather than Report.
  await userEvent.click(screen.getByRole('button', { name: 'Delete' }))
  await userEvent.click(screen.getByRole('button', { name: 'Delete' }))

  await waitFor(() => expect(mockDeletePost).toHaveBeenCalledWith('p1'))
  await waitFor(() =>
    expect(screen.queryByRole('button', { name: 'Post by ada' })).not.toBeInTheDocument(),
  )
  // post_count started at 4 and follows the deletion down to 3.
  expect(screen.getByText('3')).toBeInTheDocument()
})

test('does not offer a like control on your own posts', async () => {
  // The backend rejects liking your own post, so the grid hides the control.
  mockGetPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
  ])
  renderTab()
  await screen.findByRole('button', { name: 'Post by ada' })
  expect(screen.queryByRole('button', { name: 'Like post' })).not.toBeInTheDocument()
})

test('refresh reloads the user posts from the first page', async () => {
  mockGetPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
  ])
  renderTab()
  await screen.findByRole('button', { name: 'Post by ada' })
  expect(mockGetPosts).toHaveBeenCalledTimes(1)

  await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
  await waitFor(() => expect(mockGetPosts).toHaveBeenCalledTimes(2))
  expect(mockGetPosts).toHaveBeenLastCalledWith('ada', 0)
})

test('searches users after typing 3+ characters and navigates to a profile', async () => {
  mockGetPosts.mockResolvedValue([])
  mockSearch.mockResolvedValue([{ username: 'bob', identity_is_verified: true }])
  renderTab()

  await userEvent.type(screen.getByLabelText('Search for users'), 'bob')
  const result = await screen.findByText('bob')
  await waitFor(() => expect(mockSearch).toHaveBeenCalledWith('bob'))
  await userEvent.click(result)
  expect(screen.getByText('Profile page')).toBeInTheDocument()
})

test('does not search for queries shorter than 3 characters', async () => {
  mockGetPosts.mockResolvedValue([])
  renderTab()
  await userEvent.type(screen.getByLabelText('Search for users'), 'bo')
  // Give any (unexpected) debounce a chance to fire.
  await new Promise(r => setTimeout(r, 600))
  expect(mockSearch).not.toHaveBeenCalled()
})

test('does not request a profile when there is no signed-in user', async () => {
  vi.stubGlobal('localStorage', {
    getItem: vi.fn(() => null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  })
  renderTab()

  expect(await screen.findByText('Sign in to see your profile.')).toBeInTheDocument()
  expect(mockGetProfile).not.toHaveBeenCalled()
  expect(mockGetPosts).not.toHaveBeenCalled()
})

test('finding yourself in search clears the query instead of navigating', async () => {
  // We're already on the Profile tab, so routing to /home would be a dead tap.
  mockGetPosts.mockResolvedValue([])
  mockSearch.mockResolvedValue([{ username: 'ada', identity_is_verified: false }])
  renderTab()

  const input = screen.getByLabelText('Search for users')
  await userEvent.type(input, 'ada')
  await userEvent.click(await screen.findByText('ada'))

  expect(input).toHaveValue('')
  // Back to the profile body behind the search.
  expect(await screen.findByText('Followers')).toBeInTheDocument()
  expect(screen.queryByText('Profile page')).not.toBeInTheDocument()
})
