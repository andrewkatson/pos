import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, test, expect } from 'vitest'
import PostDetailPage from './PostDetailPage'
import type { Comment, PostDetails } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: {
    getPostDetails: vi.fn(),
    getCommentsForPost: vi.fn(),
    getCommentsForThread: vi.fn(),
    likePost: vi.fn(),
    unlikePost: vi.fn(),
    reportPost: vi.fn(),
    commentOnPost: vi.fn(),
    replyToCommentThread: vi.fn(),
    likeComment: vi.fn(),
    unlikeComment: vi.fn(),
    reportComment: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockGetDetails = vi.mocked(apiClient.getPostDetails)
const mockGetThreadRefs = vi.mocked(apiClient.getCommentsForPost)
const mockGetThreadComments = vi.mocked(apiClient.getCommentsForThread)
const mockLikePost = vi.mocked(apiClient.likePost)
const mockCommentOnPost = vi.mocked(apiClient.commentOnPost)

const post: PostDetails = {
  post_identifier: 'p1',
  image_url: 'http://img/1.jpg',
  caption: 'sunshine',
  post_likes: 3,
  author_username: 'ada',
}

const comment: Comment = {
  comment_identifier: 'c1',
  body: 'love this',
  author_username: 'bob',
  creation_time: '2024-01-01T00:00:00.000Z',
  updated_time: '2024-01-01T00:00:00.000Z',
  comment_likes: 1,
}

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/post/p1']}>
      <Routes>
        <Route path="/post/:postId" element={<PostDetailPage />} />
        <Route path="/profile/:username" element={<div>Profile page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockGetDetails.mockReset().mockResolvedValue(post)
  mockGetThreadRefs.mockReset().mockResolvedValue([])
  mockGetThreadComments.mockReset().mockResolvedValue([])
  mockLikePost.mockReset().mockResolvedValue({ message: 'ok' })
  mockCommentOnPost.mockReset().mockResolvedValue({
    comment_thread_identifier: 't1',
    comment_identifier: 'c9',
  })
})

test('renders the post caption and like count', async () => {
  renderDetail()
  expect(await screen.findByText('sunshine')).toBeInTheDocument()
  expect(screen.getByText('3 likes')).toBeInTheDocument()
})

test('liking the post calls the API and bumps the count optimistically', async () => {
  renderDetail()
  await screen.findByText('sunshine')
  await userEvent.click(screen.getByRole('button', { name: 'Like post' }))
  expect(screen.getByText('4 likes')).toBeInTheDocument()
  await waitFor(() => expect(mockLikePost).toHaveBeenCalledWith('p1'))
})

test('renders comment threads', async () => {
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([comment])
  renderDetail()
  expect(await screen.findByText('love this')).toBeInTheDocument()
  expect(screen.getByText('bob')).toBeInTheDocument()
})

test('posting a comment calls the API and reloads', async () => {
  renderDetail()
  await screen.findByText('sunshine')
  await userEvent.type(screen.getByLabelText('Add a comment'), 'nice!')
  await userEvent.click(screen.getByRole('button', { name: 'Post' }))
  await waitFor(() => expect(mockCommentOnPost).toHaveBeenCalledWith('p1', 'nice!'))
})

test('shows not-found when the post fails to load', async () => {
  mockGetDetails.mockRejectedValue(new Error('404'))
  renderDetail()
  expect(await screen.findByText('Post not found.')).toBeInTheDocument()
})
