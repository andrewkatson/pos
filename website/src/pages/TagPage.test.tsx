import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
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
