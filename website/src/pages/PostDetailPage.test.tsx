import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import PostDetailPage from './PostDetailPage'
import type { Comment, PostDetails } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: {
    isAuthenticated: vi.fn(() => true),
    getPostDetails: vi.fn(),
    getCommentsForPost: vi.fn(),
    getCommentsForThread: vi.fn(),
    getPublicPostDetails: vi.fn(),
    getPublicCommentsForPost: vi.fn(),
    getPublicCommentsForThread: vi.fn(),
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
const mockIsAuthenticated = vi.mocked(apiClient.isAuthenticated)
const mockGetPublicDetails = vi.mocked(apiClient.getPublicPostDetails)
const mockGetPublicThreadRefs = vi.mocked(apiClient.getPublicCommentsForPost)
const mockGetPublicThreadComments = vi.mocked(apiClient.getPublicCommentsForThread)
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
  mockIsAuthenticated.mockReset().mockReturnValue(true)
  mockGetDetails.mockReset().mockResolvedValue(post)
  mockGetThreadRefs.mockReset().mockResolvedValue([])
  mockGetThreadComments.mockReset().mockResolvedValue([])
  mockGetPublicDetails.mockReset().mockResolvedValue(post)
  mockGetPublicThreadRefs.mockReset().mockResolvedValue([])
  mockGetPublicThreadComments.mockReset().mockResolvedValue([])
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

test('shows how long ago the post was made', async () => {
  // Two hours ago, so the label reads at hour granularity (issue #174).
  mockGetDetails.mockResolvedValue({
    ...post,
    creation_time: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  })
  renderDetail()
  await screen.findByText('sunshine')
  expect(screen.getByText('2 hr')).toBeInTheDocument()
})

test('omits the post time when the backend response predates creation_time', async () => {
  renderDetail()
  await screen.findByText('sunshine')
  expect(document.querySelector('.detail-time')).not.toBeInTheDocument()
})

test('renders a text-only post as a caption tile and double-tap still likes (#307)', async () => {
  mockGetDetails.mockResolvedValue({ ...post, image_url: null })
  renderDetail()

  const tile = await screen.findByRole('img', { name: 'sunshine' })
  expect(tile.tagName).not.toBe('IMG')
  expect(tile).toHaveTextContent('sunshine')

  await userEvent.dblClick(tile)
  await waitFor(() => expect(mockLikePost).toHaveBeenCalledWith('p1'))
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
  // No formatting was applied, so the spans argument is undefined (#318); the
  // audience defaults to 'public' (#445).
  await waitFor(() =>
    expect(mockCommentOnPost).toHaveBeenCalledWith('p1', 'nice!', undefined, 'public'),
  )
  // The dialog closes immediately on submit so repeated taps can't double-post.
  expect(screen.queryByRole('dialog', { name: 'Add comment' })).not.toBeInTheDocument()
})

test('selecting a non-public audience threads it into commentOnPost (#445)', async () => {
  renderDetail()
  await screen.findByText('sunshine')
  await userEvent.click(screen.getByRole('button', { name: 'Add a comment...' }))
  await userEvent.type(screen.getByLabelText('Comment text'), 'family only!')
  await userEvent.selectOptions(screen.getByLabelText('Comment audience'), 'family')
  await userEvent.click(screen.getByRole('button', { name: 'Post' }))
  await waitFor(() =>
    expect(mockCommentOnPost).toHaveBeenCalledWith('p1', 'family only!', undefined, 'family'),
  )
})

test('changing the comment group filter threads the category into the listing (#445)', async () => {
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([comment])
  renderDetail()
  await screen.findByText('love this')
  // The initial load sends no category (the whole comment list).
  expect(mockGetThreadRefs).toHaveBeenCalledWith('p1', 0, undefined)
  expect(mockGetThreadComments).toHaveBeenCalledWith('t1', 0, undefined)

  await userEvent.selectOptions(
    screen.getByLabelText('Filter comments by group'),
    'friend',
  )
  // Switching the toggle reloads with the selected category threaded through
  // both the thread listing and the per-thread comment fetch.
  await waitFor(() => expect(mockGetThreadRefs).toHaveBeenCalledWith('p1', 0, 'friend'))
  await waitFor(() => expect(mockGetThreadComments).toHaveBeenCalledWith('t1', 0, 'friend'))
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

test('sharing a post copies its link when there is no OS share sheet (issue #34)', async () => {
  localStorage.setItem('username', 'someone-else')
  const writeText = vi.fn().mockResolvedValue(undefined)
  // No navigator.share in jsdom, so shareLink() falls back to the clipboard.
  vi.stubGlobal('navigator', { clipboard: { writeText } })
  renderDetail()
  await screen.findByText('sunshine')

  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  const menu = screen.getByRole('dialog', { name: 'Post options' })
  await userEvent.click(within(menu).getByRole('button', { name: 'Share' }))

  await waitFor(() =>
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/post/p1`),
  )
  // The fallback tells the user the link is now on their clipboard.
  expect(await screen.findByRole('dialog', { name: 'Link copied' })).toBeInTheDocument()
})

test('sharing a comment copies a #comment-<id> deep link (issue #34)', async () => {
  localStorage.setItem('username', 'someone-else')
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([comment])
  const writeText = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('navigator', { clipboard: { writeText } })
  renderDetail()
  await screen.findByText('love this')

  await userEvent.click(screen.getByRole('button', { name: 'Options for comment by bob' }))
  const menu = screen.getByRole('dialog', { name: 'Comment options' })
  await userEvent.click(within(menu).getByRole('button', { name: 'Share' }))

  await waitFor(() =>
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/post/p1#comment-c1`),
  )
})

// =============================================================================
// Signed out — a shared link opened by someone with no account (issue #381)
// =============================================================================

function renderSignedOut(entry = '/post/p1') {
  mockIsAuthenticated.mockReturnValue(false)
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/post/:postId" element={<PostDetailPage />} />
        <Route path="/login" element={<div>Login page</div>} />
        <Route path="/register" element={<div>Register page</div>} />
        <Route path="/profile/:username" element={<div>Profile page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

test('a signed-out visitor reads the post through the public endpoints', async () => {
  mockGetPublicThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetPublicThreadComments.mockResolvedValue([comment])
  renderSignedOut()

  expect(await screen.findByText('sunshine')).toBeInTheDocument()
  expect(await screen.findByText('love this')).toBeInTheDocument()
  expect(mockGetPublicDetails).toHaveBeenCalledWith('p1')
  expect(mockGetPublicThreadRefs).toHaveBeenCalledWith('p1', 0)
  expect(mockGetPublicThreadComments).toHaveBeenCalledWith('t1', 0)
  // No session, so the authenticated endpoints are never reached for.
  expect(mockGetDetails).not.toHaveBeenCalled()
  expect(mockGetThreadRefs).not.toHaveBeenCalled()
})

test('a signed-out visitor is no longer bounced to the login page', async () => {
  renderSignedOut()

  expect(await screen.findByText('sunshine')).toBeInTheDocument()
  expect(screen.queryByText('Login page')).not.toBeInTheDocument()
})

test('a signed-out visitor gets a sign-in prompt instead of the session-only controls', async () => {
  mockGetPublicThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetPublicThreadComments.mockResolvedValue([comment])
  renderSignedOut()
  await screen.findByText('love this')

  expect(screen.getByRole('link', { name: 'Log in' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'join' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Add a comment...' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Reply' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Like post' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Like comment' })).not.toBeInTheDocument()
  // The relationship filter needs relationships, which an anonymous visitor
  // does not have.
  expect(screen.queryByLabelText('Filter comments by group')).not.toBeInTheDocument()
  // Read-only detail is still all there.
  expect(screen.getByText('3 likes')).toBeInTheDocument()
})

test('a signed-out visitor is offered Share and nothing that needs a session', async () => {
  renderSignedOut()
  await screen.findByText('sunshine')

  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  const menu = screen.getByRole('dialog', { name: 'Post options' })
  expect(within(menu).getByRole('button', { name: 'Share' })).toBeInTheDocument()
  expect(within(menu).queryByRole('button', { name: 'Report' })).not.toBeInTheDocument()
  expect(within(menu).queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
})

test('a signed-out visitor is told a missing post may just be private', async () => {
  mockGetPublicDetails.mockRejectedValue(new Error('404'))
  renderSignedOut()

  expect(await screen.findByText('Post not found.')).toBeInTheDocument()
  expect(screen.getByText(/shared with a narrower audience/)).toBeInTheDocument()
})

// =============================================================================
// The #comment-<id> fragment a shared comment link carries (issues #34/#381)
// =============================================================================

// The fragment is only honored for a well-formed comment id, so these use real
// UUIDs rather than the short ids the rest of the file uses.
const ROOT_ID = 'bbbbbbbb-cccc-4ddd-8eee-ffffffffffff'
const REPLY_ID = '12345678-90ab-4cde-8f01-234567890abc'
const rootComment: Comment = { ...comment, comment_identifier: ROOT_ID }
const replyComment: Comment = {
  ...comment,
  comment_identifier: REPLY_ID,
  body: 'totally agree',
  author_username: 'cara',
  creation_time: '2024-01-02T00:00:00.000Z',
}

test('every comment is addressable by a #comment-<id> anchor', async () => {
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([rootComment])
  renderDetail()
  await screen.findByText('love this')

  expect(document.getElementById(`comment-${ROOT_ID}`)).toBeInTheDocument()
})

test('a shared comment link marks out the comment it points at', async () => {
  mockGetPublicThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetPublicThreadComments.mockResolvedValue([rootComment, replyComment])
  renderSignedOut(`/post/p1#comment-${REPLY_ID}`)
  await screen.findByText('totally agree')

  await waitFor(() =>
    expect(document.getElementById(`comment-${REPLY_ID}`)).toHaveClass('comment-row--shared'),
  )
  expect(document.getElementById(`comment-${ROOT_ID}`)).not.toHaveClass('comment-row--shared')
})

test('a shared comment link scrolls that comment into view', async () => {
  // The highlight and the scroll are separate mechanisms: a comment that is
  // marked but off-screen is still a broken share link, so assert the scroll
  // itself rather than inferring it from the class.
  const scrollIntoView = vi.spyOn(Element.prototype, 'scrollIntoView')
  mockGetPublicThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetPublicThreadComments.mockResolvedValue([rootComment, replyComment])
  renderSignedOut(`/post/p1#comment-${REPLY_ID}`)
  await screen.findByText('totally agree')

  await waitFor(() => expect(scrollIntoView).toHaveBeenCalled())
  expect(scrollIntoView.mock.instances[0]).toBe(document.getElementById(`comment-${REPLY_ID}`))
  scrollIntoView.mockRestore()
})

test('a plain post link scrolls nowhere', async () => {
  const scrollIntoView = vi.spyOn(Element.prototype, 'scrollIntoView')
  mockGetPublicThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetPublicThreadComments.mockResolvedValue([rootComment, replyComment])
  renderSignedOut()
  await screen.findByText('totally agree')

  expect(scrollIntoView).not.toHaveBeenCalled()
  scrollIntoView.mockRestore()
})

test('a shared comment link pages past the first batch to reach its comment', async () => {
  // The backend pages threads 10 at a time and this screen has no "load more",
  // so without this a link to a comment in the 11th thread would render a page
  // that never contains it and scroll nowhere (issue #381).
  mockGetPublicThreadRefs.mockImplementation((_postId: string, batch: number) =>
    Promise.resolve(
      batch === 0
        ? [{ comment_thread_identifier: 't1' }]
        : batch === 1
          ? [{ comment_thread_identifier: 't2' }]
          : [],
    ),
  )
  mockGetPublicThreadComments.mockImplementation((threadId: string) =>
    Promise.resolve(threadId === 't1' ? [rootComment] : [replyComment]),
  )

  renderSignedOut(`/post/p1#comment-${REPLY_ID}`)

  // The target lives in the second batch, so it had to be fetched to appear.
  expect(await screen.findByText('totally agree')).toBeInTheDocument()
  expect(mockGetPublicThreadRefs).toHaveBeenCalledWith('p1', 1)
  await waitFor(() =>
    expect(document.getElementById(`comment-${REPLY_ID}`)).toHaveClass('comment-row--shared'),
  )
  // The earlier batch stays on the page, so the comment is read in context.
  expect(screen.getByText('love this')).toBeInTheDocument()
})

test('a plain post link loads only the first batch', async () => {
  // Paging past batch 0 is strictly for reaching a shared comment; an ordinary
  // visit must not pull the whole conversation.
  mockGetPublicThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetPublicThreadComments.mockResolvedValue([rootComment])

  renderSignedOut()
  await screen.findByText('love this')

  expect(mockGetPublicThreadRefs).toHaveBeenCalledTimes(1)
  expect(mockGetPublicThreadRefs).toHaveBeenCalledWith('p1', 0)
})

test('a shared comment link that is never found stops at the batch cap', async () => {
  // A link to a since-removed or moderated comment must cost a bounded number
  // of requests, not walk the entire thread list.
  mockGetPublicThreadRefs.mockImplementation((_postId: string, batch: number) =>
    Promise.resolve(batch < 20 ? [{ comment_thread_identifier: `t${batch}` }] : []),
  )
  mockGetPublicThreadComments.mockResolvedValue([rootComment])

  renderSignedOut(`/post/p1#comment-${REPLY_ID}`)
  // Every batch returns the same comment body, so several rows carry it.
  await screen.findAllByText('love this')

  await waitFor(() => expect(mockGetPublicThreadRefs).toHaveBeenCalledTimes(5))
  // Still capped after everything settles.
  expect(mockGetPublicThreadRefs).toHaveBeenCalledTimes(5)
  expect(document.querySelector('.comment-row--shared')).toBeNull()
})

test('a plain post link marks out nothing', async () => {
  mockGetPublicThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetPublicThreadComments.mockResolvedValue([rootComment, replyComment])
  renderSignedOut()
  await screen.findByText('totally agree')

  expect(document.querySelector('.comment-row--shared')).toBeNull()
})
