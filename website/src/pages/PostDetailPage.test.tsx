import { render, screen, waitFor, within } from '@testing-library/react'
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
    retractReportPost: vi.fn(),
    deletePost: vi.fn(),
    commentOnPost: vi.fn(),
    replyToCommentThread: vi.fn(),
    likeComment: vi.fn(),
    unlikeComment: vi.fn(),
    reportComment: vi.fn(),
    retractReportComment: vi.fn(),
    deleteComment: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockGetDetails = vi.mocked(apiClient.getPostDetails)
const mockGetThreadRefs = vi.mocked(apiClient.getCommentsForPost)
const mockGetThreadComments = vi.mocked(apiClient.getCommentsForThread)
const mockLikePost = vi.mocked(apiClient.likePost)
const mockCommentOnPost = vi.mocked(apiClient.commentOnPost)
const mockDeletePost = vi.mocked(apiClient.deletePost)
const mockDeleteComment = vi.mocked(apiClient.deleteComment)
const mockReportPost = vi.mocked(apiClient.reportPost)
const mockRetractReportPost = vi.mocked(apiClient.retractReportPost)
const mockRetractReportComment = vi.mocked(apiClient.retractReportComment)

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
        <Route path="/home" element={<div>Feed page</div>} />
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
  mockDeletePost.mockReset().mockResolvedValue({ message: 'ok' })
  mockDeleteComment.mockReset().mockResolvedValue({ message: 'ok' })
  mockReportPost.mockReset().mockResolvedValue({ message: 'ok' })
  mockRetractReportPost.mockReset().mockResolvedValue({ message: 'ok' })
  mockRetractReportComment.mockReset().mockResolvedValue({ message: 'ok' })
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

test('posting a comment opens the dialog, calls the API, and dismisses', async () => {
  renderDetail()
  await screen.findByText('sunshine')
  await userEvent.click(screen.getByRole('button', { name: 'Add a comment...' }))
  await userEvent.type(screen.getByLabelText('Comment text'), 'nice!')
  await userEvent.click(screen.getByRole('button', { name: 'Post' }))
  await waitFor(() => expect(mockCommentOnPost).toHaveBeenCalledWith('p1', 'nice!'))
  // The dialog closes immediately on submit so repeated taps can't double-post.
  expect(screen.queryByRole('dialog', { name: 'Add comment' })).not.toBeInTheDocument()
})

test('collapsing a comment hides the replies below it, expanding restores them', async () => {
  const reply: Comment = {
    comment_identifier: 'c2',
    body: 'totally agree',
    author_username: 'cara',
    creation_time: '2024-01-02T00:00:00.000Z',
    updated_time: '2024-01-02T00:00:00.000Z',
    comment_likes: 0,
  }
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([comment, reply])
  renderDetail()

  // The root comment and its reply are both visible to start.
  expect(await screen.findByText('love this')).toBeInTheDocument()
  expect(screen.getByText('totally agree')).toBeInTheDocument()

  // Tapping the root comment's header collapses the thread below it.
  const collapseHeaders = screen.getAllByRole('button', { name: 'Collapse thread' })
  await userEvent.click(collapseHeaders[0])
  expect(screen.queryByText('totally agree')).not.toBeInTheDocument()
  // The root stays put and its header flips to an expand affordance.
  expect(screen.getByText('love this')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Expand thread' })).toBeInTheDocument()

  // Tapping it again expands the thread and the reply comes back.
  await userEvent.click(screen.getByRole('button', { name: 'Expand thread' }))
  expect(await screen.findByText('totally agree')).toBeInTheDocument()
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

test('refresh during an in-flight load is coalesced into one follow-up load', async () => {
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
    .mockResolvedValue(post) // coalesced follow-up run
  mockGetThreadRefs.mockResolvedValue([])

  renderDetail()
  await screen.findByText('sunshine') // initial load done

  // Post a comment -> triggers loadAll, which parks on the 2nd getPostDetails.
  await userEvent.click(screen.getByRole('button', { name: 'Add a comment...' }))
  await userEvent.type(screen.getByLabelText('Comment text'), 'hi')
  await userEvent.click(screen.getByRole('button', { name: 'Post' }))
  await waitFor(() => expect(mockGetDetails).toHaveBeenCalledTimes(2))

  // Click Refresh while that reload is still in flight: it must NOT start a
  // concurrent load (still 2 calls)...
  await userEvent.click(screen.getByRole('button', { name: 'Refresh comments' }))
  await new Promise(r => setTimeout(r, 0))
  expect(mockGetDetails).toHaveBeenCalledTimes(2)

  // ...but once the in-flight load finishes, the requested reload runs exactly
  // once (coalesced), so it isn't silently dropped.
  resolveParked(post)
  await waitFor(() => expect(mockGetDetails).toHaveBeenCalledTimes(3))
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

test('own post: the options menu offers Delete, and deleting navigates away', async () => {
  // The signed-in user authored the post, so they can't report it.
  localStorage.setItem('username', 'ada')
  renderDetail()
  await screen.findByText('sunshine')

  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  const menu = screen.getByRole('dialog', { name: 'Post options' })
  // No Report control on your own post (issue: can't report your own post).
  expect(within(menu).queryByRole('button', { name: 'Report' })).not.toBeInTheDocument()

  await userEvent.click(within(menu).getByRole('button', { name: 'Delete' }))
  // Confirm in the delete modal.
  const deleteDialog = screen.getByRole('dialog', { name: 'Delete item' })
  await userEvent.click(within(deleteDialog).getByRole('button', { name: 'Delete' }))
  await waitFor(() => expect(mockDeletePost).toHaveBeenCalledWith('p1'))
  // ...and we land on the feed, not the landing page.
  expect(await screen.findByText('Feed page')).toBeInTheDocument()
})

test('other users’ post: the options menu offers Report, and reporting works', async () => {
  // The post is by 'ada'; the signed-in user is someone else.
  localStorage.setItem('username', 'someone-else')
  renderDetail()
  await screen.findByText('sunshine')

  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  const menu = screen.getByRole('dialog', { name: 'Post options' })
  expect(within(menu).queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
  await userEvent.click(within(menu).getByRole('button', { name: 'Report' }))

  // The reason dialog opens; submitting sends the report.
  await userEvent.type(screen.getByLabelText('Reason for reporting'), 'not positive')
  await userEvent.click(screen.getByRole('button', { name: 'Submit Report' }))
  await waitFor(() => expect(mockReportPost).toHaveBeenCalledWith('p1', 'not positive'))
})

test('already-reported post: the menu offers Retract Report with the reason pre-filled', async () => {
  localStorage.setItem('username', 'someone-else')
  mockGetDetails.mockResolvedValue({
    ...post,
    is_reported: true,
    report_reason: 'felt negative',
  })
  renderDetail()
  await screen.findByText('sunshine')

  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  const menu = screen.getByRole('dialog', { name: 'Post options' })
  // Already reported: Retract replaces Report.
  expect(within(menu).queryByRole('button', { name: 'Report' })).not.toBeInTheDocument()
  await userEvent.click(within(menu).getByRole('button', { name: 'Retract Report' }))

  // The retract dialog shows the original reason pre-populated (issue #176).
  const retractDialog = screen.getByRole('dialog', { name: 'Retract report' })
  expect(within(retractDialog).getByLabelText('Your report reason')).toHaveValue('felt negative')
  await userEvent.click(within(retractDialog).getByRole('button', { name: 'Retract Report' }))
  await waitFor(() => expect(mockRetractReportPost).toHaveBeenCalledWith('p1'))
  // The reported flag clears once the retraction succeeds.
  await waitFor(() => expect(screen.queryByLabelText('Reported')).not.toBeInTheDocument())
})

test('own comment: the options menu offers Delete, and deleting reloads', async () => {
  // The signed-in user authored the comment (bob), so they can't report it.
  localStorage.setItem('username', 'bob')
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([comment])
  renderDetail()
  await screen.findByText('love this')

  await userEvent.click(screen.getByRole('button', { name: 'Options for comment by bob' }))
  const menu = screen.getByRole('dialog', { name: 'Comment options' })
  expect(within(menu).queryByRole('button', { name: 'Report' })).not.toBeInTheDocument()

  await userEvent.click(within(menu).getByRole('button', { name: 'Delete' }))
  const deleteDialog = screen.getByRole('dialog', { name: 'Delete item' })
  await userEvent.click(within(deleteDialog).getByRole('button', { name: 'Delete' }))
  await waitFor(() => expect(mockDeleteComment).toHaveBeenCalledWith('p1', 't1', 'c1'))
})

test('already-reported comment: the menu offers Retract Report with the reason pre-filled', async () => {
  localStorage.setItem('username', 'someone-else')
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([
    { ...comment, is_reported: true, report_reason: 'unkind words' },
  ])
  renderDetail()
  await screen.findByText('love this')

  await userEvent.click(screen.getByRole('button', { name: 'Options for comment by bob' }))
  const menu = screen.getByRole('dialog', { name: 'Comment options' })
  await userEvent.click(within(menu).getByRole('button', { name: 'Retract Report' }))

  const retractDialog = screen.getByRole('dialog', { name: 'Retract report' })
  expect(within(retractDialog).getByLabelText('Your report reason')).toHaveValue('unkind words')
  await userEvent.click(within(retractDialog).getByRole('button', { name: 'Retract Report' }))
  await waitFor(() =>
    expect(mockRetractReportComment).toHaveBeenCalledWith('p1', 't1', 'c1'),
  )
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
