import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, test, expect } from 'vitest'
import AppealsPage from './AppealsPage'
import type { HiddenComment, HiddenPost, MyAppeal } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: {
    isAuthenticated: vi.fn(() => true),
    getHiddenPosts: vi.fn(),
    getHiddenComments: vi.fn(),
    getMyAppeals: vi.fn(),
    submitAppeal: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockHiddenPosts = vi.mocked(apiClient.getHiddenPosts)
const mockHiddenComments = vi.mocked(apiClient.getHiddenComments)
const mockAppeals = vi.mocked(apiClient.getMyAppeals)
const mockSubmit = vi.mocked(apiClient.submitAppeal)

const hiddenPost: HiddenPost = {
  post_identifier: 'post-1',
  image_url: 'http://img/1.jpg',
  caption: 'a flagged caption',
  hidden_reason: 'classifier',
  creation_time: '2026-01-01T00:00:00Z',
  has_appeal: false,
}

const hiddenComment: HiddenComment = {
  comment_identifier: 'comment-1',
  body: 'a flagged comment',
  hidden_reason: 'reports',
  creation_time: '2026-01-01T00:00:00Z',
  has_appeal: false,
}

const pendingAppeal: MyAppeal = {
  appeal_identifier: 'appeal-1',
  target_type: 'post',
  target_identifier: 'post-9',
  status: 'pending',
  reason: 'please reconsider',
  content_snapshot: 'old caption',
  resolution_note: null,
  creation_time: '2026-01-01T00:00:00Z',
  resolved_time: null,
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/appeals']}>
      <Routes>
        <Route path="/appeals" element={<AppealsPage />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockHiddenPosts.mockReset().mockResolvedValue([])
  mockHiddenComments.mockReset().mockResolvedValue([])
  mockAppeals.mockReset().mockResolvedValue([])
  mockSubmit.mockReset().mockResolvedValue({ appeal_identifier: 'new-appeal' })
})

test('lists hidden posts and comments with their reason', async () => {
  mockHiddenPosts.mockResolvedValue([hiddenPost])
  mockHiddenComments.mockResolvedValue([hiddenComment])

  renderPage()

  expect(await screen.findByText('a flagged caption')).toBeInTheDocument()
  expect(screen.getByText('Flagged by automated review')).toBeInTheDocument()
  expect(screen.getByText('a flagged comment')).toBeInTheDocument()
  expect(screen.getByText('Hidden after user reports')).toBeInTheDocument()
})

test('shows empty states when nothing is hidden or appealed', async () => {
  renderPage()
  expect(await screen.findByText('None of your content is hidden.')).toBeInTheDocument()
  expect(screen.getByText("You haven't filed any appeals.")).toBeInTheDocument()
})

test('already-appealed content shows a status instead of a button', async () => {
  mockHiddenPosts.mockResolvedValue([{ ...hiddenPost, has_appeal: true }])
  renderPage()
  expect(await screen.findByText('Appealed')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Appeal post' })).not.toBeInTheDocument()
})

test('submitting an appeal posts the reason and reloads', async () => {
  mockHiddenPosts.mockResolvedValue([hiddenPost])
  const user = userEvent.setup()
  renderPage()

  await user.click(await screen.findByRole('button', { name: 'Appeal post' }))
  await user.type(screen.getByLabelText('Appeal reason'), 'this was a mistake')
  await user.click(screen.getByRole('button', { name: 'Submit Appeal' }))

  await waitFor(() =>
    expect(mockSubmit).toHaveBeenCalledWith({
      target_type: 'post',
      target_identifier: 'post-1',
      reason: 'this was a mistake',
    }),
  )
  // Reloaded after submit (initial load + reload).
  expect(mockHiddenPosts).toHaveBeenCalledTimes(2)
})

test('renders filed appeals with their status', async () => {
  mockAppeals.mockResolvedValue([pendingAppeal])
  renderPage()
  expect(await screen.findByText('old caption')).toBeInTheDocument()
  expect(screen.getByText('pending')).toBeInTheDocument()
})

test('surfaces a submit error and keeps the modal open', async () => {
  mockHiddenPosts.mockResolvedValue([hiddenPost])
  mockSubmit.mockRejectedValue(Object.assign(new Error('This item has already been appealed'), {}))
  const user = userEvent.setup()
  renderPage()

  await user.click(await screen.findByRole('button', { name: 'Appeal post' }))
  await user.type(screen.getByLabelText('Appeal reason'), 'again')
  await user.click(screen.getByRole('button', { name: 'Submit Appeal' }))

  expect(await screen.findByText('This item has already been appealed')).toBeInTheDocument()
})
