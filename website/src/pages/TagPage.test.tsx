import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import TagPage from './TagPage'

vi.mock('../api/client', () => ({
  apiClient: {
    isAuthenticated: vi.fn(() => true),
    getPostsByTag: vi.fn(),
    likePost: vi.fn(),
    unlikePost: vi.fn(),
    reportPost: vi.fn(),
    retractReportPost: vi.fn(),
    deletePost: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockGetPostsByTag = vi.mocked(apiClient.getPostsByTag)

function renderTagPage(tag: string) {
  return render(
    <MemoryRouter initialEntries={[`/tags/${tag}`]}>
      <Routes>
        <Route path="/tags/:tag" element={<TagPage />} />
        <Route path="/post/:postId" element={<div>Post page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockGetPostsByTag.mockReset()
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

test('shows the tag in the header and lists posts carrying it', async () => {
  mockGetPostsByTag.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'ada',
      caption: 'a #sunset',
      tags: ['sunset'],
    },
  ])

  renderTagPage('sunset')

  expect(screen.getByRole('heading', { name: '#sunset' })).toBeInTheDocument()
  expect(await screen.findByRole('button', { name: 'Post by ada' })).toBeInTheDocument()
  expect(mockGetPostsByTag).toHaveBeenCalledWith('sunset', 0)
})

test('shows an empty state when no posts carry the tag', async () => {
  mockGetPostsByTag.mockResolvedValue([])

  renderTagPage('lonely')

  expect(await screen.findByText('No posts with #lonely yet.')).toBeInTheDocument()
})

function tagPosts(start: number, count: number) {
  return Array.from({ length: count }, (_, i) => ({
    post_identifier: `p${start + i}`,
    image_url: `http://img/${start + i}.jpg`,
    author_username: 'ada',
    caption: '#sunset',
    tags: ['sunset'],
  }))
}

// jsdom has no layout: lay the grid out as 250px rows of three from the top of
// an 800px viewport, so a batch of 10 leaves both a partial row and empty space.
function stubGridLayout() {
  vi.stubGlobal('innerHeight', 800)
  return vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (
    this: HTMLElement,
  ) {
    const height = this.classList.contains('post-grid')
      ? Math.ceil(this.children.length / 3) * 250
      : 0
    return {
      top: 0,
      bottom: height,
      height,
      left: 0,
      right: 0,
      width: 0,
      x: 0,
      y: 0,
    } as DOMRect
  })
}

test('loads batches until the grid fills the screen on full rows (#538)', async () => {
  const layout = stubGridLayout()
  mockGetPostsByTag.mockImplementation(async (_tag, batch) => tagPosts(batch * 10, 10))

  renderTagPage('sunset')

  // 10 and 20 posts end on a partial row; 30 is ten full rows, past the fold.
  await waitFor(() =>
    expect(screen.getAllByRole('button', { name: 'Post by ada' })).toHaveLength(30),
  )
  expect(screen.getByRole('button', { name: 'Load more' })).toBeInTheDocument()
  expect(mockGetPostsByTag.mock.calls.map(call => call[1])).toEqual([0, 1, 2])
  layout.mockRestore()
})

test('stops filling when the tag runs out of posts (#538)', async () => {
  const layout = stubGridLayout()
  mockGetPostsByTag.mockImplementation(async (_tag, batch) => (batch === 0 ? tagPosts(0, 4) : []))

  renderTagPage('sunset')

  await waitFor(() => expect(mockGetPostsByTag).toHaveBeenCalledTimes(2))
  expect(screen.getAllByRole('button', { name: 'Post by ada' })).toHaveLength(4)
  expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument()
  expect(mockGetPostsByTag).toHaveBeenCalledTimes(2)
  layout.mockRestore()
})
