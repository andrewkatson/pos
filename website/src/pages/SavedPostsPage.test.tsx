import { StrictMode } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router'
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

function renderPageTree() {
  return (
    <MemoryRouter initialEntries={['/saved']}>
      <Routes>
        <Route path="/saved" element={<SavedPostsPage />} />
        <Route path="/login" element={<div>Login page</div>} />
        <Route path="/post/:postId" element={<div>Post page</div>} />
      </Routes>
    </MemoryRouter>
  )
}

function renderPage() {
  return render(renderPageTree())
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

test('surfaces the load error message without the misleading empty state', async () => {
  // ApiClient throws sanitized, user-facing messages; the page shows them.
  mockGetSavedPosts.mockRejectedValue(new Error('Your session has expired.'))
  renderPage()
  expect(await screen.findByText('Your session has expired.')).toBeInTheDocument()
  // The empty-state copy would wrongly claim the collection is empty on an error.
  expect(screen.queryByText("You haven't saved any posts yet.")).not.toBeInTheDocument()
})

test('falls back to generic copy when the load error carries no message', async () => {
  mockGetSavedPosts.mockRejectedValue({})
  renderPage()
  expect(await screen.findByText('Failed to load your saved posts.')).toBeInTheDocument()
})

test('overlapping first loads under StrictMode fill the grid without duplicates (#538)', async () => {
  // jsdom has no layout: 250px rows of three in an 800px viewport, so the grid
  // keeps asking for pages until it holds 30 posts.
  vi.stubGlobal('innerHeight', 800)
  const layout = vi
    .spyOn(HTMLElement.prototype, 'getBoundingClientRect')
    .mockImplementation(function (this: HTMLElement) {
      const height = this.classList.contains('post-grid')
        ? Math.ceil(this.children.length / 3) * 250
        : 0
      return { top: 0, bottom: height, height, left: 0, right: 0, width: 0, x: 0, y: 0 } as DOMRect
    })
  const page = (batch: number): FeedPost[] =>
    Array.from({ length: 10 }, (_, i) => ({
      post_identifier: `p${batch * 10 + i}`,
      image_url: null,
      author_username: 'ada',
      caption: '',
      is_saved: true,
    }))
  const settle = () => new Promise(resolve => setTimeout(resolve, 150))
  // StrictMode replays the mount effect, so page 0 is requested twice. The
  // first (superseded) load answers at once; the second (current) one and the
  // first page-1 request are held until released below.
  let releaseCurrentFirstPage: (posts: FeedPost[]) => void = () => {}
  let releaseFirstSecondPage: (posts: FeedPost[]) => void = () => {}
  let firstPageLoads = 0
  let secondPageLoads = 0
  mockGetSavedPosts.mockImplementation(batch => {
    if (batch === 0) {
      firstPageLoads += 1
      if (firstPageLoads === 1) return Promise.resolve(page(0))
      return new Promise(resolve => (releaseCurrentFirstPage = resolve))
    }
    if (batch === 1) {
      secondPageLoads += 1
      if (secondPageLoads === 1) return new Promise(resolve => (releaseFirstSecondPage = resolve))
      return Promise.resolve(page(1))
    }
    return Promise.resolve(batch === 2 ? page(2) : [])
  })

  render(<StrictMode>{renderPageTree()}</StrictMode>)

  await waitFor(() => expect(firstPageLoads).toBe(2))
  // Give the superseded load time to land and (if it were applied) start filling.
  await settle()
  releaseCurrentFirstPage(page(0))
  await settle()
  releaseFirstSecondPage(page(1))
  await waitFor(() =>
    expect(screen.getAllByRole('button', { name: 'Post by ada' })).toHaveLength(30),
  )
  await settle()
  // Without the guard, a page 1 requested off the superseded load appends again.
  expect(screen.getAllByRole('button', { name: 'Post by ada' })).toHaveLength(30)
  expect(secondPageLoads).toBe(1)
  layout.mockRestore()
})
