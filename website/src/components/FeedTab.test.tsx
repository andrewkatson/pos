import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import FeedTab from './FeedTab'

vi.mock('../api/client', () => ({
  apiClient: {
    getFeed: vi.fn(),
    getFollowedFeed: vi.fn(),
    likePost: vi.fn(),
    unlikePost: vi.fn(),
    savePost: vi.fn(),
    unsavePost: vi.fn(),
    reportPost: vi.fn(),
    retractReportPost: vi.fn(),
    deletePost: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockGetFeed = vi.mocked(apiClient.getFeed)
const mockGetFollowed = vi.mocked(apiClient.getFollowedFeed)
const mockLikePost = vi.mocked(apiClient.likePost)
const mockSavePost = vi.mocked(apiClient.savePost)
const mockDeletePost = vi.mocked(apiClient.deletePost)

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
  mockLikePost.mockReset().mockResolvedValue({ message: 'ok' })
  mockSavePost.mockReset().mockResolvedValue({ message: 'Post saved' })
  mockDeletePost.mockReset().mockResolvedValue({ message: 'ok' })
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

test('switches to the Following feed', async () => {
  mockGetFeed.mockResolvedValue([])
  mockGetFollowed.mockResolvedValue([
    { post_identifier: 'p2', image_url: 'http://img/2.jpg', author_username: 'bob', caption: 'yo' },
  ])
  renderTab()

  await userEvent.click(screen.getByRole('tab', { name: 'Following' }))
  await waitFor(() => expect(mockGetFollowed).toHaveBeenCalledWith(0))
  expect(await screen.findByRole('button', { name: 'Open post by bob' })).toBeInTheDocument()
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
  await userEvent.click(screen.getByRole('button', { name: 'Delete' }))
  await userEvent.click(screen.getByRole('button', { name: 'Delete' }))

  await waitFor(() => expect(mockDeletePost).toHaveBeenCalledWith('p1'))
  await waitFor(() =>
    expect(screen.queryByRole('button', { name: 'Open post by me' })).not.toBeInTheDocument(),
  )
  expect(mockGetFeed).toHaveBeenCalledTimes(1)
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
