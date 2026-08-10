import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router'
import { vi, beforeEach, test, expect } from 'vitest'
import LikesModal, { type LikesTarget } from './LikesModal'
import type { UserSearchResult } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: {
    getPostLikers: vi.fn(),
    getCommentLikers: vi.fn(),
  },
}))

// profilePathFor routes your own name to the Profile tab; stub the current
// username to something else so liker rows point at /profile/:username.
vi.mock('../api/session', () => ({
  getCurrentUsername: vi.fn(() => 'viewer'),
}))

import { apiClient } from '../api/client'
const mockPostLikers = vi.mocked(apiClient.getPostLikers)
const mockCommentLikers = vi.mocked(apiClient.getCommentLikers)

const POST_TARGET: LikesTarget = { kind: 'post', postIdentifier: 'post-1' }
const COMMENT_TARGET: LikesTarget = {
  kind: 'comment',
  postIdentifier: 'post-1',
  commentThreadIdentifier: 'thread-1',
  commentIdentifier: 'comment-1',
}

function liker(username: string): UserSearchResult {
  return { username, identity_is_verified: false }
}

beforeEach(() => {
  mockPostLikers.mockReset().mockResolvedValue([])
  mockCommentLikers.mockReset().mockResolvedValue([])
})

function renderModal(target: LikesTarget) {
  const onClose = vi.fn()
  render(
    <MemoryRouter initialEntries={['/post/post-1']}>
      <Routes>
        <Route path="/post/:postId" element={<LikesModal target={target} onClose={onClose} />} />
        <Route path="/profile/:username" element={<div>Profile page</div>} />
      </Routes>
    </MemoryRouter>,
  )
  return { onClose }
}

test('lists the first batch of a post’s likers', async () => {
  mockPostLikers.mockResolvedValue([liker('alice'), liker('bob')])
  renderModal(POST_TARGET)

  expect(await screen.findByText('alice')).toBeInTheDocument()
  expect(screen.getByText('bob')).toBeInTheDocument()
  expect(screen.getByRole('dialog', { name: 'Likes' })).toBeInTheDocument()
  expect(mockPostLikers).toHaveBeenCalledWith('post-1', 0)
})

test('a comment target asks the comment endpoint and is titled for it', async () => {
  mockCommentLikers.mockResolvedValue([liker('carol')])
  renderModal(COMMENT_TARGET)

  expect(await screen.findByText('carol')).toBeInTheDocument()
  expect(screen.getByRole('dialog', { name: 'Comment likes' })).toBeInTheDocument()
  expect(mockCommentLikers).toHaveBeenCalledWith('post-1', 'thread-1', 'comment-1', 0)
  expect(mockPostLikers).not.toHaveBeenCalled()
})

test('says so when nobody has liked it, and offers no Load more', async () => {
  renderModal(POST_TARGET)

  expect(await screen.findByText('No one has liked this yet.')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument()
})

test('Load more appends the next batch and stops at the end', async () => {
  const user = userEvent.setup()
  mockPostLikers
    .mockResolvedValueOnce([liker('alice')])
    .mockResolvedValueOnce([liker('bob')])
    .mockResolvedValueOnce([])
  renderModal(POST_TARGET)

  await screen.findByText('alice')
  await user.click(screen.getByRole('button', { name: 'Load more' }))

  expect(await screen.findByText('bob')).toBeInTheDocument()
  // The first batch stays listed rather than being replaced.
  expect(screen.getByText('alice')).toBeInTheDocument()
  expect(mockPostLikers).toHaveBeenLastCalledWith('post-1', 1)

  await user.click(screen.getByRole('button', { name: 'Load more' }))

  // An empty batch means the end of the list, so the control goes away.
  await waitFor(() =>
    expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument(),
  )
  expect(screen.getByText('alice')).toBeInTheDocument()
  expect(screen.getByText('bob')).toBeInTheDocument()
})

test('a failed load surfaces the error and keeps what is already listed', async () => {
  const user = userEvent.setup()
  mockPostLikers
    .mockResolvedValueOnce([liker('alice')])
    .mockRejectedValueOnce(new Error('Network is down'))
  renderModal(POST_TARGET)

  await screen.findByText('alice')
  await user.click(screen.getByRole('button', { name: 'Load more' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Network is down')
  expect(screen.getByText('alice')).toBeInTheDocument()
})

test('tapping a liker closes the dialog and opens their profile', async () => {
  const user = userEvent.setup()
  mockPostLikers.mockResolvedValue([liker('alice')])
  const { onClose } = renderModal(POST_TARGET)

  await user.click(await screen.findByRole('button', { name: /alice/ }))

  expect(onClose).toHaveBeenCalled()
  expect(await screen.findByText('Profile page')).toBeInTheDocument()
})

test('Close dismisses the dialog', async () => {
  const user = userEvent.setup()
  const { onClose } = renderModal(POST_TARGET)

  await user.click(await screen.findByRole('button', { name: 'Close' }))

  expect(onClose).toHaveBeenCalled()
})

test('a first load that fails shows the error instead of claiming nobody liked it', async () => {
  mockPostLikers.mockRejectedValue(new Error('Network is down'))
  renderModal(POST_TARGET)

  expect(await screen.findByRole('alert')).toHaveTextContent('Network is down')
  expect(screen.queryByText('No one has liked this yet.')).not.toBeInTheDocument()
})

test('switching to another target clears the previous list rather than showing it stale', async () => {
  mockPostLikers.mockResolvedValueOnce([liker('alice')])
  mockCommentLikers.mockResolvedValueOnce([liker('carol')])
  const onClose = vi.fn()
  const { rerender } = render(
    <MemoryRouter initialEntries={['/post/post-1']}>
      <LikesModal target={POST_TARGET} onClose={onClose} />
    </MemoryRouter>,
  )

  expect(await screen.findByText('alice')).toBeInTheDocument()

  rerender(
    <MemoryRouter initialEntries={['/post/post-1']}>
      <LikesModal target={COMMENT_TARGET} onClose={onClose} />
    </MemoryRouter>,
  )

  expect(await screen.findByText('carol')).toBeInTheDocument()
  expect(screen.queryByText('alice')).not.toBeInTheDocument()
})
