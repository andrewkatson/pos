import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import MyPostsTab from './MyPostsTab'

vi.mock('../api/client', () => ({
  apiClient: {
    getPostsForUser: vi.fn(),
    searchUsers: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockGetPosts = vi.mocked(apiClient.getPostsForUser)
const mockSearch = vi.mocked(apiClient.searchUsers)

function renderTab() {
  return render(
    <MemoryRouter initialEntries={['/home']}>
      <Routes>
        <Route path="/home" element={<MyPostsTab />} />
        <Route path="/post/:postId" element={<div>Post page</div>} />
        <Route path="/profile/:username" element={<div>Profile page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockGetPosts.mockReset()
  mockSearch.mockReset()
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

test('renders the current user post grid and opens a post', async () => {
  mockGetPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
  ])
  renderTab()
  const cell = await screen.findByRole('button', { name: 'Post by ada' })
  await userEvent.click(cell)
  expect(screen.getByText('Post page')).toBeInTheDocument()
})

test('shows empty state when the user has no posts', async () => {
  mockGetPosts.mockResolvedValue([])
  renderTab()
  expect(await screen.findByText("You haven't posted anything yet.")).toBeInTheDocument()
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
