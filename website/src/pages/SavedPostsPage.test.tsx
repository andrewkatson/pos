import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import SavedPostsPage from './SavedPostsPage'
import type { FeedPost } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: {
    isAuthenticated: vi.fn(() => true),
    getSavedPosts: vi.fn(),
    savePost: vi.fn(),
    unsavePost: vi.fn(),
    likePost: vi.fn(),
    unlikePost: vi.fn(),
    reportPost: vi.fn(),
    retractReportPost: vi.fn(),
    deletePost: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockIsAuthenticated = vi.mocked(apiClient.isAuthenticated)
const mockGetSavedPosts = vi.mocked(apiClient.getSavedPosts)
const mockUnsavePost = vi.mocked(apiClient.unsavePost)

const savedPosts: FeedPost[] = [
  {
    post_identifier: 'p1',
    image_url: 'http://img/1.jpg',
    author_username: 'ada',
    caption: 'first',
    is_saved: true,
  },
  {
    post_identifier: 'p2',
    image_url: 'http://img/2.jpg',
    author_username: 'bob',
    caption: 'second',
    is_saved: true,
  },
]

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/saved']}>
      <Routes>
        <Route path="/saved" element={<SavedPostsPage />} />
        <Route path="/login" element={<div>Login page</div>} />
        <Route path="/post/:postId" element={<div>Post page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockIsAuthenticated.mockReset().mockReturnValue(true)
  mockGetSavedPosts.mockReset().mockResolvedValue([])
  mockUnsavePost.mockReset().mockResolvedValue({ message: 'Post unsaved' })
  vi.stubGlobal('localStorage', {
    getItem: vi.fn(() => 'me'),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('redirects to login when not authenticated', async () => {
  mockIsAuthenticated.mockReturnValue(false)
  renderPage()
  expect(await screen.findByText('Login page')).toBeInTheDocument()
  expect(mockGetSavedPosts).not.toHaveBeenCalled()
})

test('lists the saved posts', async () => {
  mockGetSavedPosts.mockResolvedValue(savedPosts)
  renderPage()

  expect(await screen.findByRole('button', { name: 'Post by ada' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Post by bob' })).toBeInTheDocument()
  // Both come back already saved, so their bookmark controls offer to unsave.
  expect(screen.getAllByRole('button', { name: 'Unsave post' })).toHaveLength(2)
})

test('shows an empty state when nothing is saved', async () => {
  renderPage()
  expect(await screen.findByText("You haven't saved any posts yet.")).toBeInTheDocument()
})

test('unsaving a post calls unsavePost and drops the tile', async () => {
  mockGetSavedPosts.mockResolvedValue(savedPosts)
  renderPage()

  await screen.findByRole('button', { name: 'Post by ada' })
  await userEvent.click(screen.getAllByRole('button', { name: 'Unsave post' })[0])

  await waitFor(() => expect(mockUnsavePost).toHaveBeenCalledWith('p1'))
  await waitFor(() =>
    expect(screen.queryByRole('button', { name: 'Post by ada' })).not.toBeInTheDocument(),
  )
  // The other saved post is untouched.
  expect(screen.getByRole('button', { name: 'Post by bob' })).toBeInTheDocument()
})

test('a failed unsave surfaces an error and keeps the tile', async () => {
  mockGetSavedPosts.mockResolvedValue(savedPosts)
  mockUnsavePost.mockRejectedValue(new Error('Rate limited'))
  renderPage()

  await screen.findByRole('button', { name: 'Post by ada' })
  await userEvent.click(screen.getAllByRole('button', { name: 'Unsave post' })[0])

  expect(await screen.findByText('Rate limited')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Post by ada' })).toBeInTheDocument()
})

test('surfaces a load error without the misleading empty state', async () => {
  mockGetSavedPosts.mockRejectedValue(new Error('boom'))
  renderPage()
  expect(await screen.findByText('Failed to load your saved posts.')).toBeInTheDocument()
  // The empty-state copy would wrongly claim the collection is empty on an error.
  expect(screen.queryByText("You haven't saved any posts yet.")).not.toBeInTheDocument()
})
