import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, test, expect } from 'vitest'
import FeedTab from './FeedTab'

vi.mock('../api/client', () => ({
  apiClient: {
    getFeed: vi.fn(),
    getFollowedFeed: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockGetFeed = vi.mocked(apiClient.getFeed)
const mockGetFollowed = vi.mocked(apiClient.getFollowedFeed)

function renderTab() {
  return render(
    <MemoryRouter initialEntries={['/home']}>
      <Routes>
        <Route path="/home" element={<FeedTab />} />
        <Route path="/post/:postId" element={<div>Post page</div>} />
        <Route path="/profile/:username" element={<div>Profile page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockGetFeed.mockReset()
  mockGetFollowed.mockReset()
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
