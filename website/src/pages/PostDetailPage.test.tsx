import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import PostDetailPage from './PostDetailPage'
import type { Comment, PostDetails } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: {
    isAuthenticated: vi.fn(() => true),
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

// In-memory localStorage so getCurrentUsername() can be controlled per test.
const store = new Map<string, string>()

beforeEach(() => {
  store.clear()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => store.set(key, value),
    removeItem: (key: string) => store.delete(key),
    clear: () => store.clear(),
  })
  mockGetDetails.mockReset().mockResolvedValue(post)
  mockGetThreadRefs.mockReset().mockResolvedValue([])
  mockGetThreadComments.mockReset().mockResolvedValue([])
  mockLikePost.mockReset().mockResolvedValue({ message: 'ok' })
  mockCommentOnPost.mockReset().mockResolvedValue({
    comment_thread_identifier: 't1',
    comment_identifier: 'c9',
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
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

test('hides the like control on the current user’s own post', async () => {
  // The signed-in user authored the post, so the backend would reject a like.
  localStorage.setItem('username', 'ada')
  renderDetail()
  await screen.findByText('sunshine')
  expect(screen.queryByRole('button', { name: 'Like post' })).not.toBeInTheDocument()
  // The like count is still shown.
  expect(screen.getByText('3 likes')).toBeInTheDocument()
})

test('hides the like control on the current user’s own comment', async () => {
  // The signed-in user authored the comment, so the backend would reject a like.
  localStorage.setItem('username', 'bob')
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([comment])
  renderDetail()
  await screen.findByText('love this')
  expect(screen.queryByRole('button', { name: 'Like comment' })).not.toBeInTheDocument()
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

test('refresh reloads the post and comments', async () => {
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([comment])
  renderDetail()
  await screen.findByText('love this')
  expect(mockGetThreadRefs).toHaveBeenCalledTimes(1)

  await userEvent.click(screen.getByRole('button', { name: 'Refresh comments' }))
  await waitFor(() => expect(mockGetThreadRefs).toHaveBeenCalledTimes(2))
  expect(mockGetDetails).toHaveBeenCalledTimes(2)
})

test('refresh does not start a second concurrent load while one is in flight', async () => {
  // 1st (initial) load resolves; 2nd load (the post-comment reload) is parked so
  // it stays in flight while we click Refresh.
  let resolveParked!: (v: PostDetails) => void
  const parked = new Promise<PostDetails>(r => {
    resolveParked = r
  })
  mockGetDetails
    .mockReset()
    .mockResolvedValueOnce(post) // initial load
    .mockReturnValueOnce(parked) // reload after posting a comment (parked)
    .mockResolvedValue(post)
  mockGetThreadRefs.mockResolvedValue([])

  renderDetail()
  await screen.findByText('sunshine') // initial load done

  // Post a comment -> triggers loadAll, which parks on the 2nd getPostDetails.
  await userEvent.type(screen.getByLabelText('Add a comment'), 'hi')
  await userEvent.click(screen.getByRole('button', { name: 'Post' }))
  await waitFor(() => expect(mockGetDetails).toHaveBeenCalledTimes(2))

  // Click Refresh while that reload is still in flight — the shared guard must
  // drop it rather than firing a third concurrent load.
  await userEvent.click(screen.getByRole('button', { name: 'Refresh comments' }))
  await new Promise(r => setTimeout(r, 0))
  expect(mockGetDetails).toHaveBeenCalledTimes(2)

  // Let the parked load finish; still no extra call.
  resolveParked(post)
  await waitFor(() => expect(mockGetDetails).toHaveBeenCalledTimes(2))
})

test('shows not-found when the post fails to load', async () => {
  mockGetDetails.mockRejectedValue(new Error('404'))
  renderDetail()
  expect(await screen.findByText('Post not found.')).toBeInTheDocument()
})

test('still shows the post when only the comments fail to load', async () => {
  mockGetThreadRefs.mockRejectedValue(new Error('network'))
  renderDetail()
  // The post itself loaded, so it renders rather than the not-found state.
  expect(await screen.findByText('sunshine')).toBeInTheDocument()
  expect(screen.queryByText('Post not found.')).not.toBeInTheDocument()
  expect(await screen.findByText('Failed to load comments.')).toBeInTheDocument()
})

test('redirects to login when unauthenticated', () => {
  vi.mocked(apiClient.isAuthenticated).mockReturnValueOnce(false)
  render(
    <MemoryRouter initialEntries={['/post/p1']}>
      <Routes>
        <Route path="/post/:postId" element={<PostDetailPage />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  )
  expect(screen.getByText('Login page')).toBeInTheDocument()
})
