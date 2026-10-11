import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router'
import { vi, beforeEach, test, expect } from 'vitest'
import FollowRequestsPage from './FollowRequestsPage'
import type { UserSearchResult } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: {
    isAuthenticated: vi.fn(() => true),
    getFollowRequests: vi.fn(),
    approveFollowRequest: vi.fn(),
    denyFollowRequest: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockIsAuthenticated = vi.mocked(apiClient.isAuthenticated)
const mockGetRequests = vi.mocked(apiClient.getFollowRequests)
const mockApprove = vi.mocked(apiClient.approveFollowRequest)
const mockDeny = vi.mocked(apiClient.denyFollowRequest)

const requests: UserSearchResult[] = [
  { username: 'alice', identity_is_verified: true },
  { username: 'bob', identity_is_verified: false },
]

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/follow-requests']}>
      <Routes>
        <Route path="/follow-requests" element={<FollowRequestsPage />} />
        <Route path="/login" element={<div>Login page</div>} />
        <Route path="/profile/:username" element={<div>Profile page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockIsAuthenticated.mockReset().mockReturnValue(true)
  mockGetRequests.mockReset().mockResolvedValue([])
  mockApprove.mockReset().mockResolvedValue({ message: 'Follow request approved' })
  mockDeny.mockReset().mockResolvedValue({ message: 'Follow request denied' })
})

test('redirects to login when not authenticated', async () => {
  mockIsAuthenticated.mockReturnValue(false)
  renderPage()
  expect(await screen.findByText('Login page')).toBeInTheDocument()
  expect(mockGetRequests).not.toHaveBeenCalled()
})

test('shows an empty state when nobody is waiting', async () => {
  renderPage()
  expect(await screen.findByText('No one is waiting to follow you.')).toBeInTheDocument()
})

test('lists requests with approve and deny for each', async () => {
  mockGetRequests.mockResolvedValue(requests)
  renderPage()

  expect(await screen.findByRole('link', { name: 'alice' })).toHaveAttribute('href', '/profile/alice')
  expect(screen.getByRole('button', { name: 'Approve bob' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Deny bob' })).toBeInTheDocument()
})

test('approving removes the row', async () => {
  mockGetRequests.mockResolvedValue(requests)
  renderPage()

  await userEvent.click(await screen.findByRole('button', { name: 'Approve alice' }))

  await waitFor(() => expect(mockApprove).toHaveBeenCalledWith('alice'))
  await waitFor(() => expect(screen.queryByRole('link', { name: 'alice' })).not.toBeInTheDocument())
  expect(screen.getByRole('link', { name: 'bob' })).toBeInTheDocument()
})

test('denying removes the row', async () => {
  mockGetRequests.mockResolvedValue(requests)
  renderPage()

  await userEvent.click(await screen.findByRole('button', { name: 'Deny bob' }))

  await waitFor(() => expect(mockDeny).toHaveBeenCalledWith('bob'))
  expect(mockApprove).not.toHaveBeenCalled()
  await waitFor(() => expect(screen.queryByRole('link', { name: 'bob' })).not.toBeInTheDocument())
})

test('a failed decision keeps the row and shows the error', async () => {
  mockGetRequests.mockResolvedValue(requests)
  mockApprove.mockRejectedValue({ message: 'No follow request from user' })
  renderPage()

  await userEvent.click(await screen.findByRole('button', { name: 'Approve alice' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('No follow request from user')
  expect(screen.getByRole('link', { name: 'alice' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Approve alice' })).toBeEnabled()
})

test('a failed load shows the error, not the empty state', async () => {
  mockGetRequests.mockRejectedValue({ message: 'Server unavailable' })
  renderPage()

  expect(await screen.findByRole('alert')).toHaveTextContent('Server unavailable')
  expect(screen.queryByText('No one is waiting to follow you.')).not.toBeInTheDocument()
})
