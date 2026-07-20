import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import MyPostsTab from './MyPostsTab'

vi.mock('../api/client', () => ({
  apiClient: {
    getPostsForUser: vi.fn(),
    searchUsers: vi.fn(),
    getPostStatus: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockGetPosts = vi.mocked(apiClient.getPostsForUser)
const mockSearch = vi.mocked(apiClient.searchUsers)
const mockGetPostStatus = vi.mocked(apiClient.getPostStatus)

function renderTab() {
  return render(
    <MemoryRouter initialEntries={['/home']}>
      <Routes>
        <Route path="/home" element={<MyPostsTab />} />
        <Route path="/post/:postId" element={<div>Post page</div>} />
        <Route path="/profile/:username" element={<div>Profile page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockGetPosts.mockReset()
  mockSearch.mockReset()
  mockGetPostStatus.mockReset()
  vi.stubGlobal('localStorage', {
    getItem: vi.fn(() => 'ada'),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('renders the current user post grid and opens a post', async () => {
  mockGetPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
  ])
  renderTab()
  const cell = await screen.findByRole('button', { name: 'Post by ada' })
  await userEvent.click(cell)
  expect(screen.getByText('Post page')).toBeInTheDocument()
})

test('falls back to the original image when the compressed one fails to load', async () => {
  // The compressed copy is produced by an async Lambda, so a just-posted (or
  // recently hidden) image can 404 in the compressed bucket for a while. The
  // grid should fall back to the full-resolution original rather than showing a
  // broken image (issues #252/#254).
  mockGetPosts.mockResolvedValue([
    {
      post_identifier: 'p1',
      image_url: 'http://compressed/1.jpg',
      original_image_url: 'http://original/1.jpg',
      author_username: 'ada',
      caption: 'hi',
    },
  ])
  renderTab()
  const img = (await screen.findByAltText('hi')) as HTMLImageElement
  expect(img.getAttribute('src')).toBe('http://compressed/1.jpg')

  // Simulate the compressed image failing to load.
  fireEvent.error(img)
  expect(img.getAttribute('src')).toBe('http://original/1.jpg')

  // A second failure (e.g. the original also 404s) must not loop back.
  fireEvent.error(img)
  expect(img.getAttribute('src')).toBe('http://original/1.jpg')
})

test('shows empty state when the user has no posts', async () => {
  mockGetPosts.mockResolvedValue([])
  renderTab()
  expect(await screen.findByText("You haven't posted anything yet.")).toBeInTheDocument()
})

test('refresh does not get stuck loading when there is no signed-in user', async () => {
  vi.stubGlobal('localStorage', {
    getItem: vi.fn(() => null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  })
  mockGetPosts.mockResolvedValue([])
  renderTab()

  const refresh = await screen.findByRole('button', { name: 'Refresh' })
  await userEvent.click(refresh)

  // loadPosts early-returns with no user; the button must reset rather than
  // stay disabled with the spinner stuck on.
  await waitFor(() => expect(screen.getByRole('button', { name: 'Refresh' })).toBeEnabled())
  expect(mockGetPosts).not.toHaveBeenCalled()
})

test('refresh reloads the user posts from the first page', async () => {
  mockGetPosts.mockResolvedValue([
    { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
  ])
  renderTab()
  await screen.findByRole('button', { name: 'Post by ada' })
  expect(mockGetPosts).toHaveBeenCalledTimes(1)

  await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
  await waitFor(() => expect(mockGetPosts).toHaveBeenCalledTimes(2))
  expect(mockGetPosts).toHaveBeenLastCalledWith('ada', 0)
})

test('searches users after typing 3+ characters and navigates to a profile', async () => {
  mockGetPosts.mockResolvedValue([])
  mockSearch.mockResolvedValue([{ username: 'bob', identity_is_verified: true }])
  renderTab()

  await userEvent.type(screen.getByLabelText('Search for users'), 'bob')
  const result = await screen.findByText('bob')
  await waitFor(() => expect(mockSearch).toHaveBeenCalledWith('bob'))
  await userEvent.click(result)
  expect(screen.getByText('Profile page')).toBeInTheDocument()
})

test('shows an In review badge on a pending post and clears it once approved (#282)', async () => {
  // Classification is asynchronous: the grid shows the author's pending post
  // with an "In review" badge and a short bounded poll reconciles the outcome.
  vi.useFakeTimers({ shouldAdvanceTime: true })
  try {
    mockGetPosts
      .mockResolvedValueOnce([
        {
          post_identifier: 'p1',
          image_url: null,
          author_username: 'ada',
          caption: 'hi',
          status: 'pending',
          hidden: true,
          hidden_reason: 'pending_classification',
        },
      ])
      .mockResolvedValue([
        {
          post_identifier: 'p1',
          image_url: null,
          author_username: 'ada',
          caption: 'hi',
          status: 'approved',
          hidden: false,
          hidden_reason: '',
        },
      ])
    mockGetPostStatus.mockResolvedValue({
      post_identifier: 'p1',
      status: 'approved',
      reason_code: null,
      appealable: false,
      hidden: false,
      hidden_reason: '',
    })
    renderTab()

    expect(await screen.findByText('In review')).toBeInTheDocument()
    // The review state is part of the accessible name so assistive tech
    // announces it (the visual badge alone is hidden behind the aria-label).
    expect(screen.getByRole('button', { name: 'Post by ada — In review' })).toBeInTheDocument()

    await vi.advanceTimersByTimeAsync(3100)
    await waitFor(() => expect(mockGetPostStatus).toHaveBeenCalledWith('p1'))
    // The resolved status triggers a grid reload, which drops the badge.
    await waitFor(() => expect(screen.queryByText('In review')).not.toBeInTheDocument())
  } finally {
    vi.useRealTimers()
  }
})

test('surfaces a rejection notice when the status poll resolves to rejected (#282)', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  try {
    mockGetPosts
      .mockResolvedValueOnce([
        {
          post_identifier: 'p1',
          image_url: null,
          author_username: 'ada',
          caption: 'hi',
          status: 'pending',
          hidden: true,
          hidden_reason: 'pending_classification',
        },
      ])
      .mockResolvedValue([
        {
          post_identifier: 'p1',
          image_url: null,
          author_username: 'ada',
          caption: 'hi',
          status: 'rejected',
          hidden: true,
          hidden_reason: 'classifier',
          appealable: true,
        },
      ])
    mockGetPostStatus.mockResolvedValue({
      post_identifier: 'p1',
      status: 'rejected',
      reason_code: 'guidelines',
      appealable: true,
      hidden: true,
      hidden_reason: 'classifier',
      message:
        'Your post did not pass automated review because it did not meet our positivity guidelines. It is hidden for now but you can appeal the decision.',
    })
    renderTab()

    expect(await screen.findByText('In review')).toBeInTheDocument()

    await vi.advanceTimersByTimeAsync(3100)
    expect(await screen.findByRole('alert')).toHaveTextContent(/you can appeal/i)
    // The reloaded grid marks the post as hidden-but-appealable.
    expect(await screen.findByText('Hidden — you can appeal')).toBeInTheDocument()
  } finally {
    vi.useRealTimers()
  }
})

test('does not poll when no post is pending (#282)', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  try {
    mockGetPosts.mockResolvedValue([
      { post_identifier: 'p1', image_url: 'http://img/1.jpg', author_username: 'ada', caption: 'hi' },
    ])
    renderTab()
    await screen.findByRole('button', { name: 'Post by ada' })

    await vi.advanceTimersByTimeAsync(10000)
    expect(mockGetPostStatus).not.toHaveBeenCalled()
  } finally {
    vi.useRealTimers()
  }
})

test('does not search for queries shorter than 3 characters', async () => {
  mockGetPosts.mockResolvedValue([])
  renderTab()
  await userEvent.type(screen.getByLabelText('Search for users'), 'bo')
  // Give any (unexpected) debounce a chance to fire.
  await new Promise(r => setTimeout(r, 600))
  expect(mockSearch).not.toHaveBeenCalled()
})
