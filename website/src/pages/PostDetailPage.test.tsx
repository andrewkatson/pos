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
    getPostLikers: vi.fn(),
    getCommentLikers: vi.fn(),
    reportPost: vi.fn(),
    retractReportPost: vi.fn(),
    deletePost: vi.fn(),
    lockComments: vi.fn(),
    unlockComments: vi.fn(),
    commentOnPost: vi.fn(),
    replyToCommentThread: vi.fn(),
    likeComment: vi.fn(),
    unlikeComment: vi.fn(),
    reportComment: vi.fn(),
    retractReportComment: vi.fn(),
    deleteComment: vi.fn(),
    editPost: vi.fn(),
    editComment: vi.fn(),
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
const mockLockComments = vi.mocked(apiClient.lockComments)
const mockUnlockComments = vi.mocked(apiClient.unlockComments)
const mockDeleteComment = vi.mocked(apiClient.deleteComment)
const mockReportPost = vi.mocked(apiClient.reportPost)
const mockRetractReportPost = vi.mocked(apiClient.retractReportPost)
const mockRetractReportComment = vi.mocked(apiClient.retractReportComment)
const mockGetPostLikers = vi.mocked(apiClient.getPostLikers)
const mockGetCommentLikers = vi.mocked(apiClient.getCommentLikers)
const mockEditPost = vi.mocked(apiClient.editPost)
const mockEditComment = vi.mocked(apiClient.editComment)

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
  mockLockComments.mockReset().mockResolvedValue({ comments_disabled: true })
  mockUnlockComments.mockReset().mockResolvedValue({ comments_disabled: false })
  mockDeleteComment.mockReset().mockResolvedValue({ message: 'ok' })
  mockReportPost.mockReset().mockResolvedValue({ message: 'ok' })
  mockRetractReportPost.mockReset().mockResolvedValue({ message: 'ok' })
  mockRetractReportComment.mockReset().mockResolvedValue({ message: 'ok' })
  mockGetPostLikers.mockReset().mockResolvedValue([])
  mockGetCommentLikers.mockReset().mockResolvedValue([])
  mockEditPost.mockReset().mockImplementation(async (_id, caption) => ({
    caption,
    edited_time: '2024-01-02T00:00:00.000Z',
    tags: [],
  }))
  mockEditComment.mockReset().mockImplementation(async (_p, _t, _c, text, formatting) => ({
    body: text,
    body_formatting: formatting ?? null,
    edited_time: '2024-01-02T00:00:00.000Z',
  }))
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

// ---- Audience badge (issue #518) ----

test('shows who can see your own post', async () => {
  localStorage.setItem('username', 'ada')
  mockGetDetails.mockResolvedValue({ ...post, audience: 'following' })
  renderDetail()
  await screen.findByText('sunshine')
  expect(screen.getByLabelText('Visible to people you follow')).toHaveTextContent('Following')
})

test("shows no audience badge on someone else's post", async () => {
  localStorage.setItem('username', 'bob')
  mockGetDetails.mockResolvedValue({ ...post, audience: 'following' })
  renderDetail()
  await screen.findByText('sunshine')
  expect(document.querySelector('.audience-badge')).not.toBeInTheDocument()
})

test('shows who can see your own comment, and nothing on anyone else’s', async () => {
  localStorage.setItem('username', 'bob')
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([
    { ...comment, audience: 'family' },
    {
      ...comment,
      comment_identifier: 'c2',
      body: 'so pretty',
      author_username: 'ada',
      audience: 'family',
    },
  ])
  renderDetail()
  await screen.findByText('love this')
  await screen.findByText('so pretty')
  // Exactly one badge: bob's own comment. ada's family-only comment carries no
  // badge for bob even though it has an audience — that's ada's information.
  expect(screen.getAllByLabelText('Visible to family only')).toHaveLength(1)
  expect(document.querySelectorAll('.audience-badge')).toHaveLength(1)
})

test('labels your own comment public when the payload has no audience', async () => {
  localStorage.setItem('username', 'bob')
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([comment])
  renderDetail()
  await screen.findByText('love this')
  expect(screen.getByLabelText('Visible to anyone')).toBeInTheDocument()
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

test('does not show a collapse control when a comment has no replies', async () => {
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([comment])
  renderDetail()

  expect(await screen.findByText('love this')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Collapse thread' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Expand thread' })).not.toBeInTheDocument()
})

test('loads the next comment page before deciding which comments have replies', async () => {
  const firstPage: Comment[] = Array.from({ length: 30 }, (_, index) => ({
    ...comment,
    comment_identifier: `c${index + 1}`,
    body: `comment ${index + 1}`,
    creation_time: new Date(Date.UTC(2024, 0, index + 1)).toISOString(),
  }))
  const nextPage: Comment[] = [{
    ...comment,
    comment_identifier: 'c31',
    body: 'comment 31',
    creation_time: new Date(Date.UTC(2024, 1, 1)).toISOString(),
  }]
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockImplementation((_threadId, batch) =>
    Promise.resolve(batch === 0 ? firstPage : nextPage),
  )
  renderDetail()

  expect(await screen.findByText('comment 31')).toBeInTheDocument()
  expect(mockGetThreadComments).toHaveBeenCalledWith('t1', 0, undefined)
  expect(mockGetThreadComments).toHaveBeenCalledWith('t1', 1, undefined)
  expect(screen.getAllByRole('button', { name: 'Collapse thread' })).toHaveLength(30)
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
  // Only the root has another comment below it; the last reply has nothing to fold.
  expect(screen.getAllByRole('button', { name: 'Collapse thread' })).toHaveLength(1)

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

test('the three-dots button announces whether its menu is open', async () => {
  localStorage.setItem('username', 'someone-else')
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([comment])
  renderDetail()
  await screen.findByText('love this')

  const postButton = screen.getByRole('button', { name: 'Post options' })
  const commentButton = screen.getByRole('button', { name: 'Options for comment by bob' })
  expect(postButton).toHaveAttribute('aria-expanded', 'false')

  await userEvent.click(postButton)
  expect(postButton).toHaveAttribute('aria-expanded', 'true')
  // Only the item whose menu is open says so.
  expect(commentButton).toHaveAttribute('aria-expanded', 'false')

  // Escape closes the menu, and the button goes back to collapsed.
  await userEvent.keyboard('{Escape}')
  expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  expect(postButton).toHaveAttribute('aria-expanded', 'false')
})

test('own post: the options menu offers Delete, and deleting navigates away', async () => {
  // The signed-in user authored the post, so they can't report it.
  localStorage.setItem('username', 'ada')
  renderDetail()
  await screen.findByText('sunshine')

  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  const menu = screen.getByRole('menu', { name: 'Post options' })
  // No Report control on your own post (issue: can't report your own post).
  expect(within(menu).queryByRole('menuitem', { name: 'Report' })).not.toBeInTheDocument()

  await userEvent.click(within(menu).getByRole('menuitem', { name: 'Delete' }))
  // Confirm in the delete modal.
  const deleteDialog = screen.getByRole('dialog', { name: 'Delete item' })
  await userEvent.click(within(deleteDialog).getByRole('button', { name: 'Delete' }))
  await waitFor(() => expect(mockDeletePost).toHaveBeenCalledWith('p1'))
  // ...and we land on the feed, not the landing page.
  expect(await screen.findByText('Feed page')).toBeInTheDocument()
})

test('own post: the options menu offers to turn off commenting, and the composer swaps for a notice (#492)', async () => {
  localStorage.setItem('username', 'ada')
  renderDetail()
  await screen.findByText('sunshine')
  expect(screen.getByRole('button', { name: 'Add a comment...' })).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  const menu = screen.getByRole('menu', { name: 'Post options' })
  await userEvent.click(within(menu).getByRole('menuitem', { name: 'Turn off commenting' }))

  await waitFor(() => expect(mockLockComments).toHaveBeenCalledWith('p1'))
  // The composer trigger is replaced by a plain notice once comments are off.
  expect(screen.queryByRole('button', { name: 'Add a comment...' })).not.toBeInTheDocument()
  expect(screen.getByText('Comments are turned off for this post.')).toBeInTheDocument()
})

test('own post with comments already off: the menu offers to turn commenting back on', async () => {
  localStorage.setItem('username', 'ada')
  mockGetDetails.mockResolvedValue({ ...post, comments_disabled: true })
  renderDetail()
  await screen.findByText('sunshine')
  expect(screen.getByText('Comments are turned off for this post.')).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  const menu = screen.getByRole('menu', { name: 'Post options' })
  await userEvent.click(within(menu).getByRole('menuitem', { name: 'Turn on commenting' }))

  await waitFor(() => expect(mockUnlockComments).toHaveBeenCalledWith('p1'))
  expect(await screen.findByRole('button', { name: 'Add a comment...' })).toBeInTheDocument()
})

test("someone else's post: the options menu never offers to lock comments", async () => {
  localStorage.setItem('username', 'someone-else')
  renderDetail()
  await screen.findByText('sunshine')

  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  const menu = screen.getByRole('menu', { name: 'Post options' })
  expect(within(menu).queryByRole('menuitem', { name: 'Turn off commenting' })).not.toBeInTheDocument()
  expect(within(menu).queryByRole('menuitem', { name: 'Turn on commenting' })).not.toBeInTheDocument()
})

test('other users’ post: the options menu offers Report, and reporting works', async () => {
  // The post is by 'ada'; the signed-in user is someone else.
  localStorage.setItem('username', 'someone-else')
  renderDetail()
  await screen.findByText('sunshine')

  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  const menu = screen.getByRole('menu', { name: 'Post options' })
  expect(within(menu).queryByRole('menuitem', { name: 'Delete' })).not.toBeInTheDocument()
  await userEvent.click(within(menu).getByRole('menuitem', { name: 'Report' }))

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
  const menu = screen.getByRole('menu', { name: 'Post options' })
  // Already reported: Retract replaces Report.
  expect(within(menu).queryByRole('menuitem', { name: 'Report' })).not.toBeInTheDocument()
  await userEvent.click(within(menu).getByRole('menuitem', { name: 'Retract Report' }))

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
  const menu = screen.getByRole('menu', { name: 'Comment options' })
  expect(within(menu).queryByRole('menuitem', { name: 'Report' })).not.toBeInTheDocument()

  await userEvent.click(within(menu).getByRole('menuitem', { name: 'Delete' }))
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
  const menu = screen.getByRole('menu', { name: 'Comment options' })
  await userEvent.click(within(menu).getByRole('menuitem', { name: 'Retract Report' }))

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
  const menu = screen.getByRole('menu', { name: 'Post options' })
  await userEvent.click(within(menu).getByRole('menuitem', { name: 'Share' }))

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
  const menu = screen.getByRole('menu', { name: 'Comment options' })
  await userEvent.click(within(menu).getByRole('menuitem', { name: 'Share' }))

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
  const menu = screen.getByRole('menu', { name: 'Post options' })
  expect(within(menu).getByRole('menuitem', { name: 'Share' })).toBeInTheDocument()
  expect(within(menu).queryByRole('menuitem', { name: 'Report' })).not.toBeInTheDocument()
  expect(within(menu).queryByRole('menuitem', { name: 'Delete' })).not.toBeInTheDocument()
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

// ---- Who liked this (issue #478) ----

test('the like count on your own post opens the likers dialog', async () => {
  localStorage.setItem('username', 'ada')
  mockGetPostLikers.mockResolvedValue([{ username: 'grace', identity_is_verified: false }])
  renderDetail()

  await userEvent.click(
    await screen.findByRole('button', { name: '3 likes, see who liked this' }),
  )

  expect(await screen.findByRole('dialog', { name: 'Likes' })).toBeInTheDocument()
  expect(screen.getByText('grace')).toBeInTheDocument()
  expect(mockGetPostLikers).toHaveBeenCalledWith('p1', 0)
})

test("the like count on someone else's post is plain text", async () => {
  localStorage.setItem('username', 'someone-else')
  renderDetail()

  await screen.findByText('sunshine')
  expect(screen.getByText('3 likes')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /see who liked this/ })).not.toBeInTheDocument()
  expect(mockGetPostLikers).not.toHaveBeenCalled()
})

test('the like count on your own comment opens the comment likers dialog', async () => {
  localStorage.setItem('username', 'bob')
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([comment])
  mockGetCommentLikers.mockResolvedValue([{ username: 'grace', identity_is_verified: false }])
  renderDetail()

  await userEvent.click(
    await screen.findByRole('button', { name: '1 like, see who liked this comment' }),
  )

  expect(await screen.findByRole('dialog', { name: 'Comment likes' })).toBeInTheDocument()
  expect(screen.getByText('grace')).toBeInTheDocument()
  expect(mockGetCommentLikers).toHaveBeenCalledWith('p1', 't1', 'c1', 0)
})

test("the like count on someone else's comment is plain text", async () => {
  localStorage.setItem('username', 'ada')
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([comment])
  renderDetail()

  await screen.findByText('love this')
  expect(
    screen.queryByRole('button', { name: /see who liked this comment/ }),
  ).not.toBeInTheDocument()
  expect(mockGetCommentLikers).not.toHaveBeenCalled()
})

test('own post: Edit opens the composer prefilled with the caption and saves it (#462)', async () => {
  localStorage.setItem('username', 'ada')
  renderDetail()
  await screen.findByText('sunshine')

  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  await userEvent.click(
    within(screen.getByRole('menu', { name: 'Post options' })).getByRole('menuitem', { name: 'Edit' }),
  )
  const dialog = screen.getByRole('dialog', { name: 'Edit caption' })
  const field = within(dialog).getByLabelText('Caption text')
  expect(field).toHaveValue('sunshine')
  // A caption is styled whole, and keeps its audience — neither control shows.
  expect(within(dialog).queryByRole('group', { name: 'Text formatting' })).not.toBeInTheDocument()
  expect(within(dialog).queryByLabelText('Comment audience')).not.toBeInTheDocument()

  await userEvent.clear(field)
  await userEvent.type(field, 'moonlight')
  await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))

  await waitFor(() => expect(mockEditPost).toHaveBeenCalledWith('p1', 'moonlight'))
  expect(await screen.findByText('moonlight')).toBeInTheDocument()
  expect(screen.getByText(/edited/)).toBeInTheDocument()
  expect(screen.queryByRole('dialog', { name: 'Edit caption' })).not.toBeInTheDocument()
})

test('a rejected caption edit keeps the original and shows why (#462)', async () => {
  localStorage.setItem('username', 'ada')
  mockEditPost.mockRejectedValue(new Error('Your edit was not saved.'))
  renderDetail()
  await screen.findByText('sunshine')

  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  await userEvent.click(
    within(screen.getByRole('menu', { name: 'Post options' })).getByRole('menuitem', { name: 'Edit' }),
  )
  const field = screen.getByLabelText('Caption text')
  await userEvent.clear(field)
  await userEvent.type(field, 'gloom')
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Your edit was not saved.')
  expect(screen.getByText('sunshine')).toBeInTheDocument()
})

test("someone else's post offers no Edit (#462)", async () => {
  renderDetail()
  await screen.findByText('sunshine')
  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  expect(
    within(screen.getByRole('menu', { name: 'Post options' })).queryByRole('menuitem', { name: 'Edit' }),
  ).not.toBeInTheDocument()
})

test('own pending post offers no Edit (#462)', async () => {
  localStorage.setItem('username', 'ada')
  mockGetDetails.mockResolvedValue({ ...post, hidden: true, status: 'pending' })
  renderDetail()
  await screen.findByText('sunshine')
  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  expect(
    within(screen.getByRole('menu', { name: 'Post options' })).queryByRole('menuitem', { name: 'Edit' }),
  ).not.toBeInTheDocument()
})

test('own comment: Edit opens the composer prefilled with its text and formatting (#462)', async () => {
  localStorage.setItem('username', 'bob')
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([
    {
      ...comment,
      body_formatting: [{ start: 0, end: 4, bold: true, italic: false, size: 'normal' }],
    },
  ])
  renderDetail()
  await screen.findByText('love')

  await userEvent.click(screen.getByRole('button', { name: 'Options for comment by bob' }))
  await userEvent.click(
    within(screen.getByRole('menu', { name: 'Comment options' })).getByRole('menuitem', { name: 'Edit' }),
  )
  const dialog = screen.getByRole('dialog', { name: 'Edit comment' })
  const field = within(dialog).getByLabelText('Comment text')
  expect(field).toHaveValue('love this')
  // The formatting toolbar is there; the audience picker is not — an edit
  // keeps who the comment was shared with.
  expect(within(dialog).getByRole('group', { name: 'Text formatting' })).toBeInTheDocument()
  expect(within(dialog).queryByLabelText('Comment audience')).not.toBeInTheDocument()

  await userEvent.type(field, ' a lot')
  await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))

  // The existing bold span over "love" survives the edit.
  await waitFor(() =>
    expect(mockEditComment).toHaveBeenCalledWith('p1', 't1', 'c1', 'love this a lot', [
      { start: 0, end: 4, bold: true, italic: false, size: 'normal' },
    ]),
  )
  expect(await screen.findByText(/edited/)).toBeInTheDocument()
})

test("someone else's comment offers no Edit (#462)", async () => {
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([comment])
  renderDetail()
  await screen.findByText('love this')
  await userEvent.click(screen.getByRole('button', { name: 'Options for comment by bob' }))
  expect(
    within(screen.getByRole('menu', { name: 'Comment options' })).queryByRole('menuitem', { name: 'Edit' }),
  ).not.toBeInTheDocument()
})

test('your own comment on a post with comments turned off offers no Edit (#462)', async () => {
  localStorage.setItem('username', 'bob')
  mockGetDetails.mockResolvedValue({ ...post, comments_disabled: true })
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([comment])
  renderDetail()
  await screen.findByText('love this')
  await userEvent.click(screen.getByRole('button', { name: 'Options for comment by bob' }))
  expect(
    within(screen.getByRole('menu', { name: 'Comment options' })).queryByRole('menuitem', { name: 'Edit' }),
  ).not.toBeInTheDocument()
})

test('an edited comment is labelled as edited (#462)', async () => {
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([{ ...comment, edited_time: '2024-01-02T00:00:00.000Z' }])
  renderDetail()
  await screen.findByText('love this')
  expect(screen.getByText(/edited/)).toBeInTheDocument()
})

test("an edit keeps a comment's surrounding whitespace, so restyling stays formatting-only (#462)", async () => {
  localStorage.setItem('username', 'bob')
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  // The mobile composers save text untrimmed.
  mockGetThreadComments.mockResolvedValue([{ ...comment, body: 'love this ' }])
  renderDetail()
  await screen.findByText(/love this/)

  await userEvent.click(screen.getByRole('button', { name: 'Options for comment by bob' }))
  await userEvent.click(
    within(screen.getByRole('menu', { name: 'Comment options' })).getByRole('menuitem', { name: 'Edit' }),
  )
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))

  await waitFor(() =>
    expect(mockEditComment).toHaveBeenCalledWith('p1', 't1', 'c1', 'love this ', undefined),
  )
})

test('a refresh that returns the pre-edit post keeps the saved caption (#462)', async () => {
  localStorage.setItem('username', 'ada')
  renderDetail()
  await screen.findByText('sunshine')

  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  await userEvent.click(
    within(screen.getByRole('menu', { name: 'Post options' })).getByRole('menuitem', { name: 'Edit' }),
  )
  const field = screen.getByLabelText('Caption text')
  await userEvent.clear(field)
  await userEvent.type(field, 'moonlight')
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('moonlight')).toBeInTheDocument()

  // mockGetDetails still answers with the original, never-edited post — a
  // response to a request sent before the save.
  await userEvent.click(screen.getByRole('button', { name: 'Refresh comments' }))
  await waitFor(() => expect(mockGetDetails).toHaveBeenCalledTimes(2))
  expect(screen.getByText('moonlight')).toBeInTheDocument()
  expect(screen.queryByText('sunshine')).not.toBeInTheDocument()
})

test('a refresh that returns the pre-edit comment keeps the saved edit (#462)', async () => {
  localStorage.setItem('username', 'bob')
  mockGetThreadRefs.mockResolvedValue([{ comment_thread_identifier: 't1' }])
  mockGetThreadComments.mockResolvedValue([comment])
  renderDetail()
  await screen.findByText('love this')

  await userEvent.click(screen.getByRole('button', { name: 'Options for comment by bob' }))
  await userEvent.click(
    within(screen.getByRole('menu', { name: 'Comment options' })).getByRole('menuitem', { name: 'Edit' }),
  )
  const field = screen.getByLabelText('Comment text')
  await userEvent.type(field, ' a lot')
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('love this a lot')).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: 'Refresh comments' }))
  await waitFor(() => expect(mockGetDetails).toHaveBeenCalledTimes(2))
  expect(await screen.findByText('love this a lot')).toBeInTheDocument()
})

test('a refresh carrying a later edit made elsewhere replaces the saved one (#462)', async () => {
  localStorage.setItem('username', 'ada')
  renderDetail()
  await screen.findByText('sunshine')

  await userEvent.click(screen.getByRole('button', { name: 'Post options' }))
  await userEvent.click(
    within(screen.getByRole('menu', { name: 'Post options' })).getByRole('menuitem', { name: 'Edit' }),
  )
  const field = screen.getByLabelText('Caption text')
  await userEvent.clear(field)
  await userEvent.type(field, 'moonlight')
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('moonlight')).toBeInTheDocument()

  // The save above is stamped 2024-01-02; this one is a day later.
  mockGetDetails.mockResolvedValue({
    ...post,
    caption: 'starlight',
    edited_time: '2024-01-03T00:00:00.000Z',
  })
  await userEvent.click(screen.getByRole('button', { name: 'Refresh comments' }))
  expect(await screen.findByText('starlight')).toBeInTheDocument()
})
