import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import FeedTab from './FeedTab'
import type { FeedPost } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: {
    getFeed: vi.fn(),
    getFollowedFeed: vi.fn(),
    getTopPosts: vi.fn(),
    getPostLikers: vi.fn(),
    likePost: vi.fn(),
    unlikePost: vi.fn(),
    savePost: vi.fn(),
    unsavePost: vi.fn(),
    reportPost: vi.fn(),
    retractReportPost: vi.fn(),
    deletePost: vi.fn(),
    lockComments: vi.fn(),
    unlockComments: vi.fn(),
    editPost: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockGetFeed = vi.mocked(apiClient.getFeed)
const mockGetFollowed = vi.mocked(apiClient.getFollowedFeed)
const mockGetTop = vi.mocked(apiClient.getTopPosts)
const mockLikePost = vi.mocked(apiClient.likePost)
const mockSavePost = vi.mocked(apiClient.savePost)
const mockDeletePost = vi.mocked(apiClient.deletePost)
const mockLockComments = vi.mocked(apiClient.lockComments)
const mockGetPostLikers = vi.mocked(apiClient.getPostLikers)
const mockEditPost = vi.mocked(apiClient.editPost)

function renderTab() {
  return render(
    <MemoryRouter initialEntries={['/feed']}>
      <Routes>
        <Route path="/feed" element={<FeedTab />} />
        {/* The real /home renders the app shell, which opens on the Profile
            tab — that's where your own name should land (issue #347). */}
        <Route path="/home" element={<div>Profile tab</div>} />
        <Route path="/post/:postId" element={<div>Post page</div>} />
        <Route path="/profile/:username" element={<div>Profile page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockGetFeed.mockReset()
  mockGetFollowed.mockReset()
  mockGetTop.mockReset()
  mockLikePost.mockReset().mockResolvedValue({ message: 'ok' })
  mockSavePost.mockReset().mockResolvedValue({ message: 'Post saved' })
  mockDeletePost.mockReset().mockResolvedValue({ message: 'ok' })
  mockLockComments.mockReset().mockResolvedValue({ comments_disabled: true })
  mockGetPostLikers.mockReset().mockResolvedValue([])
  mockEditPost.mockReset().mockImplementation(async (_id, caption) => ({
    caption,
    edited_time: '2024-01-02T00:00:00.000Z',
    tags: [],
  }))
  // getCurrentUsername reads storage; 'ada' is another user in these feeds
  // unless a test says otherwise.
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

test('loads the For You feed by default and opens a post', async () => {
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await userEvent.click(await screen.findByRole('button', { name: 'Open post by ada' }))
  expect(screen.getByText('Post page')).toBeInTheDocument()
})

test('renders a text-only post as a caption tile instead of an image (#307)', async () => {
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: null, author_username: 'ada', caption: 'words only' },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  const tile = await screen.findByRole('img', { name: 'words only' })
  expect(tile.tagName).not.toBe('IMG')
  expect(tile).toHaveTextContent('words only')
})

test('shows the caption under the photo for an image post (#378)', async () => {
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'a lovely day' },
  ])
  mockGetFollowed.mockResolvedValue([])
  const { container } = renderTab()

  await screen.findByRole('button', { name: 'Open post by ada' })
  const caption = container.querySelector('.feed-post__caption')
  expect(caption).toHaveTextContent('a lovely day')
})

test("applies the author's caption font to the feed caption (#450)", async () => {
  mockGetFeed.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'ada',
      caption: 'a lovely day',
      caption_font: 'serif',
    },
  ])
  mockGetFollowed.mockResolvedValue([])
  const { container } = renderTab()

  await screen.findByRole('button', { name: 'Open post by ada' })
  expect(container.querySelector('.feed-post__caption')).toHaveClass('caption-font--serif')
})

test('leaves the feed caption unstyled when the post has no font (#450)', async () => {
  // Older payloads omit caption_font, and `default` means "no override" — either
  // way the caption keeps the feed's own styling and gains no font class.
  mockGetFeed.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'ada',
      caption: 'a lovely day',
      caption_font: 'default',
    },
  ])
  mockGetFollowed.mockResolvedValue([])
  const { container } = renderTab()

  await screen.findByRole('button', { name: 'Open post by ada' })
  expect(container.querySelector('.feed-post__caption')).toHaveClass('feed-post__caption')
  expect(container.querySelector('[class*="caption-font--"]')).toBeNull()
})

test('does not repeat the caption below a text-only post (#378)', async () => {
  // The tile above already shows it; a second copy underneath would be redundant.
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: null, author_username: 'ada', caption: 'words only' },
  ])
  mockGetFollowed.mockResolvedValue([])
  const { container } = renderTab()

  await screen.findByRole('img', { name: 'words only' })
  expect(container.querySelector('.feed-post__caption')).toBeNull()
})

test('switches to the Following feed', async () => {
  mockGetFeed.mockResolvedValue([])
  mockGetFollowed.mockResolvedValue([
    { post_identifier: 'p2', image_url: 'http://img/2.jpg', author_username: 'bob', caption: 'yo' },
  ])
  renderTab()

  await userEvent.click(screen.getByRole('tab', { name: 'Following' }))
  await waitFor(() => expect(mockGetFollowed).toHaveBeenCalledWith(0, undefined))
  expect(await screen.findByRole('button', { name: 'Open post by bob' })).toBeInTheDocument()
})

test('filters the Following feed by relationship group (#392)', async () => {
  mockGetFeed.mockResolvedValue([])
  mockGetFollowed.mockResolvedValue([
    { post_identifier: 'p2', image_url: 'http://img/2.jpg', author_username: 'bob', caption: 'yo' },
  ])
  renderTab()

  await userEvent.click(screen.getByRole('tab', { name: 'Following' }))
  await waitFor(() => expect(mockGetFollowed).toHaveBeenCalledWith(0, undefined))

  await userEvent.selectOptions(
    screen.getByLabelText('Filter following feed by group'),
    'family',
  )
  await waitFor(() => expect(mockGetFollowed).toHaveBeenLastCalledWith(0, 'family'))
})

test('the group filter is hidden on the For You feed (#392)', () => {
  mockGetFeed.mockResolvedValue([])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  expect(
    screen.queryByLabelText('Filter following feed by group'),
  ).not.toBeInTheDocument()
})

test('shows the Top scoreboard for this week by default, ranked (#558)', async () => {
  mockGetFeed.mockResolvedValue([])
  mockGetTop.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'best' },
    { post_identifier: 'p2', image_url: 'http://img/2.jpg', author_username: 'bob', caption: 'next' },
  ])
  renderTab()

  await userEvent.click(screen.getByRole('tab', { name: 'Top' }))
  await waitFor(() => expect(mockGetTop).toHaveBeenCalledWith(0, 'week'))
  expect(await screen.findByLabelText('Rank 1')).toHaveTextContent('#1')
  expect(screen.getByLabelText('Rank 2')).toHaveTextContent('#2')
  expect(screen.getByLabelText('Top posts time period')).toHaveValue('week')
})

test('changing the Top period reloads the scoreboard (#558)', async () => {
  mockGetFeed.mockResolvedValue([])
  mockGetTop.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'best' },
  ])
  renderTab()

  await userEvent.click(screen.getByRole('tab', { name: 'Top' }))
  await waitFor(() => expect(mockGetTop).toHaveBeenCalledWith(0, 'week'))

  await userEvent.selectOptions(screen.getByLabelText('Top posts time period'), 'year')
  await waitFor(() => expect(mockGetTop).toHaveBeenCalledWith(0, 'year'))
})

test('a slow response for the previous period does not overwrite the new one (#558)', async () => {
  mockGetFeed.mockResolvedValue([])
  let resolveWeek: (posts: FeedPost[]) => void = () => {}
  mockGetTop.mockImplementation((_batch, period) =>
    period === 'week'
      ? new Promise<FeedPost[]>(resolve => {
          resolveWeek = resolve
        })
      : Promise.resolve([
          { post_identifier: 'y1', image_url: 'http://img/y.jpg', author_username: 'yearly', caption: 'y' },
        ]),
  )
  renderTab()

  await userEvent.click(screen.getByRole('tab', { name: 'Top' }))
  await waitFor(() => expect(mockGetTop).toHaveBeenCalledWith(0, 'week'))
  await userEvent.selectOptions(screen.getByLabelText('Top posts time period'), 'year')
  expect(await screen.findByRole('button', { name: 'Open post by yearly' })).toBeInTheDocument()

  // The Week request finally lands; it must be ignored.
  resolveWeek([
    { post_identifier: 'w1', image_url: 'http://img/w.jpg', author_username: 'weekly', caption: 'w' },
  ])
  await new Promise(resolve => setTimeout(resolve, 0))
  expect(screen.queryByRole('button', { name: 'Open post by weekly' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Open post by yearly' })).toBeInTheDocument()
})

test('switching to a feed that fails to load does not keep the old posts (#558)', async () => {
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
  ])
  mockGetTop.mockRejectedValue(new Error('boom'))
  renderTab()

  await screen.findByRole('button', { name: 'Open post by ada' })
  await userEvent.click(screen.getByRole('tab', { name: 'Top' }))
  await waitFor(() => expect(mockGetTop).toHaveBeenCalled())

  expect(screen.queryByRole('button', { name: 'Open post by ada' })).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Rank 1')).not.toBeInTheDocument()
  expect(await screen.findByText('No posts here yet.')).toBeInTheDocument()
})

test('a post repeated across Top pages is only listed once (#558)', async () => {
  mockGetFeed.mockResolvedValue([])
  const post = (id: string) => ({
    post_identifier: id,
    image_url: `http://img/${id}.jpg`,
    author_username: `author_${id}`,
    caption: id,
  })
  mockGetTop.mockImplementation(batch =>
    Promise.resolve(batch === 0 ? [post('a'), post('b')] : [post('b'), post('c')]),
  )
  renderTab()

  await userEvent.click(screen.getByRole('tab', { name: 'Top' }))
  await screen.findByRole('button', { name: 'Open post by author_b' })
  await userEvent.click(screen.getByRole('button', { name: 'Load more' }))
  await screen.findByRole('button', { name: 'Open post by author_c' })

  expect(screen.getAllByRole('button', { name: 'Open post by author_b' })).toHaveLength(1)
  expect(screen.getByLabelText('Rank 3')).toBeInTheDocument()
  expect(screen.queryByLabelText('Rank 4')).not.toBeInTheDocument()
})

test('Load more skips past a Top page of nothing but repeats (#558)', async () => {
  mockGetFeed.mockResolvedValue([])
  const post = (id: string) => ({
    post_identifier: id,
    image_url: `http://img/${id}.jpg`,
    author_username: `author_${id}`,
    caption: id,
  })
  const pages: Record<number, ReturnType<typeof post>[]> = {
    0: [post('a'), post('b')],
    1: [post('a'), post('b')],
    2: [post('c')],
  }
  mockGetTop.mockImplementation(batch => Promise.resolve(pages[batch] ?? []))
  renderTab()

  await userEvent.click(screen.getByRole('tab', { name: 'Top' }))
  await screen.findByRole('button', { name: 'Open post by author_b' })
  await userEvent.click(screen.getByRole('button', { name: 'Load more' }))

  // One click reaches page 2's new post instead of stalling on page 1.
  expect(await screen.findByRole('button', { name: 'Open post by author_c' })).toBeInTheDocument()
  expect(mockGetTop).toHaveBeenCalledWith(2, 'week')
})

test('the period picker and ranks are only on the Top feed (#558)', async () => {
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
  ])
  renderTab()

  await screen.findByRole('button', { name: 'Open post by ada' })
  expect(screen.queryByLabelText('Top posts time period')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Rank 1')).not.toBeInTheDocument()
})

test('navigates to an author profile from the feed', async () => {
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await userEvent.click(await screen.findByRole('button', { name: 'ada' }))
  expect(screen.getByText('Profile page')).toBeInTheDocument()
})

test('refresh reloads the feed from the first page', async () => {
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await screen.findByRole('button', { name: 'Open post by ada' })
  expect(mockGetFeed).toHaveBeenCalledTimes(1)

  await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
  await waitFor(() => expect(mockGetFeed).toHaveBeenCalledTimes(2))
  expect(mockGetFeed).toHaveBeenLastCalledWith(0)
})

// ---- In-place post actions on the feed (issue #267) ----

test('likes a post straight from the feed', async () => {
  mockGetFeed.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'ada',
      caption: 'hi',
      post_likes: 1,
      is_liked: false,
    },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await userEvent.click(await screen.findByRole('button', { name: 'Like post' }))
  await waitFor(() => expect(mockLikePost).toHaveBeenCalledWith('p1'))
  expect(await screen.findByRole('button', { name: 'Unlike post' })).toBeInTheDocument()
  expect(screen.getByText('2')).toBeInTheDocument()
})

test('saves a post straight from the feed (#193)', async () => {
  mockGetFeed.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'ada',
      caption: 'hi',
      is_saved: false,
    },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await userEvent.click(await screen.findByRole('button', { name: 'Save post' }))
  await waitFor(() => expect(mockSavePost).toHaveBeenCalledWith('p1'))
  // The control flips to offer unsaving, and the row stays on the feed.
  expect(await screen.findByRole('button', { name: 'Unsave post' })).toBeInTheDocument()
})

test('deleting your own post removes it without reloading the feed', async () => {
  // Reloading would reshuffle the weighted ordering under the user, so the row
  // is dropped locally instead.
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'me', caption: 'mine' },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await userEvent.click(await screen.findByRole('button', { name: 'Options for post by me' }))
  // The menu row, then the confirmation modal's button.
  await userEvent.click(screen.getByRole('menuitem', { name: 'Delete' }))
  await userEvent.click(screen.getByRole('button', { name: 'Delete' }))

  await waitFor(() => expect(mockDeletePost).toHaveBeenCalledWith('p1'))
  await waitFor(() =>
    expect(screen.queryByRole('button', { name: 'Open post by me' })).not.toBeInTheDocument(),
  )
  expect(mockGetFeed).toHaveBeenCalledTimes(1)
})

test('turning off commenting from the feed menu closes the menu (#492)', async () => {
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'me', caption: 'mine' },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await userEvent.click(await screen.findByRole('button', { name: 'Options for post by me' }))
  await userEvent.click(screen.getByRole('menuitem', { name: 'Turn off commenting' }))

  await waitFor(() => expect(mockLockComments).toHaveBeenCalledWith('p1'))
  expect(screen.queryByRole('menu')).not.toBeInTheDocument()

  // Reopening offers the opposite action.
  await userEvent.click(screen.getByRole('button', { name: 'Options for post by me' }))
  expect(screen.getByRole('menuitem', { name: 'Turn on commenting' })).toBeInTheDocument()
})

test('editing your own caption from the feed menu updates the row in place (#462)', async () => {
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'me', caption: 'mine' },
  ])
  mockGetFollowed.mockResolvedValue([])
  const { container } = renderTab()

  await userEvent.click(await screen.findByRole('button', { name: 'Options for post by me' }))
  await userEvent.click(screen.getByRole('menuitem', { name: 'Edit' }))
  const field = screen.getByLabelText('Caption text')
  expect(field).toHaveValue('mine')
  await userEvent.clear(field)
  await userEvent.type(field, 'still mine')
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))

  await waitFor(() => expect(mockEditPost).toHaveBeenCalledWith('p1', 'still mine'))
  await waitFor(() =>
    expect(container.querySelector('.feed-post__caption')).toHaveTextContent('still mine'),
  )
  // No reload: that would reshuffle the weighted feed under the user.
  expect(mockGetFeed).toHaveBeenCalledTimes(1)
})

test('a refreshed row edited elsewhere replaces the locally saved caption (#462)', async () => {
  mockGetFeed
    .mockResolvedValueOnce([
      { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'me', caption: 'mine' },
    ])
    .mockResolvedValue([
      {
        post_identifier: 'p1',
        image_url: 'http://img/1.jpg',
        author_username: 'me',
        caption: 'edited on my phone',
        edited_time: '2024-01-03T00:00:00.000Z',
      },
    ])
  mockGetFollowed.mockResolvedValue([])
  const { container } = renderTab()

  await userEvent.click(await screen.findByRole('button', { name: 'Options for post by me' }))
  await userEvent.click(screen.getByRole('menuitem', { name: 'Edit' }))
  const field = screen.getByLabelText('Caption text')
  await userEvent.clear(field)
  await userEvent.type(field, 'still mine')
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() =>
    expect(container.querySelector('.feed-post__caption')).toHaveTextContent('still mine'),
  )

  // The local save is stamped 2024-01-02; the refreshed row's later edit wins.
  await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
  await waitFor(() =>
    expect(container.querySelector('.feed-post__caption')).toHaveTextContent('edited on my phone'),
  )
})

test("the feed menu offers no Edit on someone else's post or your own pending one (#462)", async () => {
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hers' },
    {
      post_identifier: 'p2',
      image_url: 'http://img/2.jpg',
      author_username: 'me',
      caption: 'mine',
      hidden: true,
      status: 'pending',
    },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await userEvent.click(await screen.findByRole('button', { name: 'Options for post by ada' }))
  expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument()
  await userEvent.keyboard('{Escape}')
  await userEvent.click(screen.getByRole('button', { name: 'Options for post by me' }))
  expect(screen.queryByRole('menuitem', { name: 'Edit' })).not.toBeInTheDocument()
})

test('hides the like control on your own post in the feed', async () => {
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'me', caption: 'mine' },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await screen.findByRole('button', { name: 'Open post by me' })
  expect(screen.queryByRole('button', { name: 'Like post' })).not.toBeInTheDocument()
})

// ---- Audience badge (issue #518) ----

test('shows who can see your own post on its feed row', async () => {
  mockGetFeed.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'me',
      caption: 'mine',
      audience: 'family',
    },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await screen.findByRole('button', { name: 'Open post by me' })
  // Feed rows have room for the label, not just the icon.
  expect(screen.getByLabelText('Visible to family only')).toHaveTextContent('Family')
})

test('labels your own post public when the payload has no audience', async () => {
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'me', caption: 'mine' },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await screen.findByRole('button', { name: 'Open post by me' })
  expect(screen.getByLabelText('Visible to anyone')).toBeInTheDocument()
})

test("shows no audience badge on someone else's post", async () => {
  mockGetFeed.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'ada',
      caption: 'hi',
      audience: 'friends',
    },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await screen.findByRole('button', { name: 'Open post by ada' })
  expect(document.querySelector('.audience-badge')).not.toBeInTheDocument()
})

// ---- Feed row detail (issue #249) ----

test('shows the comment count and opens the post when it is tapped', async () => {
  mockGetFeed.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'ada',
      caption: 'hi',
      comment_count: 3,
    },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  const comments = await screen.findByRole('button', { name: '3 comments, open post' })
  await userEvent.click(comments)
  expect(screen.getByText('Post page')).toBeInTheDocument()
})

test('pluralizes a single comment', async () => {
  mockGetFeed.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'ada',
      caption: 'hi',
      comment_count: 1,
    },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()
  expect(await screen.findByRole('button', { name: '1 comment, open post' })).toBeInTheDocument()
})

test('shows how long ago the post was made', async () => {
  const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString()
  mockGetFeed.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'ada',
      caption: 'hi',
      creation_time: twoHoursAgo,
    },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()
  expect(await screen.findByText('2 hr')).toBeInTheDocument()
})

test('omits the comment count when the payload has no comment_count', async () => {
  // Older responses predate the field; showing "0 comments" would assert there
  // are none rather than that we don't know.
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await screen.findByRole('button', { name: 'Open post by ada' })
  expect(screen.queryByRole('button', { name: /comments?, open post$/ })).not.toBeInTheDocument()
})

test('omits the time when the post has no creation timestamp', async () => {
  // Older responses predate the field; the row should just drop the label.
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()
  await screen.findByRole('button', { name: 'Open post by ada' })
  expect(screen.queryByText(/^\d+ (min|hr|days?|weeks?|years?)$/)).not.toBeInTheDocument()
})

test('tapping your own name in the feed goes to the Profile tab', async () => {
  // Not the /profile/:username route, which is the pushed copy for other users
  // (issue #347).
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'me', caption: 'mine' },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await userEvent.click(await screen.findByRole('button', { name: 'me' }))
  expect(screen.getByText('Profile tab')).toBeInTheDocument()
})

test('tapping another user name in the feed goes to their profile page', async () => {
  mockGetFeed.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await userEvent.click(await screen.findByRole('button', { name: 'ada' }))
  expect(screen.getByText('Profile page')).toBeInTheDocument()
})

// ---- Who liked this (issue #478) ----

test('the like count on your own feed row opens the likers dialog', async () => {
  mockGetFeed.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'me',
      caption: 'mine',
      post_likes: 2,
    },
  ])
  mockGetFollowed.mockResolvedValue([])
  mockGetPostLikers.mockResolvedValue([
    { username: 'ada', identity_is_verified: false },
    { username: 'grace', identity_is_verified: false },
  ])
  renderTab()

  await userEvent.click(
    await screen.findByRole('button', { name: '2 likes, see who liked this' }),
  )

  expect(await screen.findByText('ada')).toBeInTheDocument()
  expect(screen.getByText('grace')).toBeInTheDocument()
  expect(mockGetPostLikers).toHaveBeenCalledWith('p1', 0)
})

test("the like count on someone else's feed row is not tappable", async () => {
  mockGetFeed.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://img/1.jpg',
      author_username: 'ada',
      caption: 'hi',
      post_likes: 2,
    },
  ])
  mockGetFollowed.mockResolvedValue([])
  renderTab()

  await screen.findByRole('button', { name: 'Open post by ada' })
  expect(
    screen.queryByRole('button', { name: /see who liked this/ }),
  ).not.toBeInTheDocument()
  expect(mockGetPostLikers).not.toHaveBeenCalled()
})
