import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, test, expect } from 'vitest'
import BlockedUsersPage from './BlockedUsersPage'
import type { UserSearchResult } from '../api/types'

vi.mock('../api/client', () => ({
  apiClient: {
    isAuthenticated: vi.fn(() => true),
    getBlockedUsers: vi.fn(),
    toggleBlock: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockIsAuthenticated = vi.mocked(apiClient.isAuthenticated)
const mockGetBlockedUsers = vi.mocked(apiClient.getBlockedUsers)
const mockToggleBlock = vi.mocked(apiClient.toggleBlock)

const blockedUsers: UserSearchResult[] = [
  { username: 'alice', identity_is_verified: true },
  { username: 'bob', identity_is_verified: false },
]

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/blocked']}>
      <Routes>
        <Route path="/blocked" element={<BlockedUsersPage />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockIsAuthenticated.mockReset().mockReturnValue(true)
  mockGetBlockedUsers.mockReset().mockResolvedValue([])
  mockToggleBlock.mockReset().mockResolvedValue({ message: 'User unblocked' })
})

test('redirects to login when not authenticated', async () => {
  mockIsAuthenticated.mockReturnValue(false)
  renderPage()
  expect(await screen.findByText('Login page')).toBeInTheDocument()
  expect(mockGetBlockedUsers).not.toHaveBeenCalled()
})

test('lists blocked users with an unblock button each', async () => {
  mockGetBlockedUsers.mockResolvedValue(blockedUsers)

  renderPage()

  expect(await screen.findByText('alice')).toBeInTheDocument()
  expect(screen.getByText('bob')).toBeInTheDocument()
  expect(screen.getAllByRole('button', { name: 'Unblock' })).toHaveLength(2)
  // Only alice is identity-verified.
  expect(screen.getAllByLabelText('Verified')).toHaveLength(1)
})

test('shows an empty state when nobody is blocked', async () => {
  renderPage()
  expect(await screen.findByText("You haven't blocked anyone.")).toBeInTheDocument()
})

test('unblocking a user calls toggleBlock and removes the row', async () => {
  mockGetBlockedUsers.mockResolvedValue(blockedUsers)
  const user = userEvent.setup()
  renderPage()

  await screen.findByText('alice')
  await user.click(screen.getAllByRole('button', { name: 'Unblock' })[0])

  await waitFor(() => expect(mockToggleBlock).toHaveBeenCalledWith('alice'))
  await waitFor(() => expect(screen.queryByText('alice')).not.toBeInTheDocument())
  // bob is still listed.
  expect(screen.getByText('bob')).toBeInTheDocument()
})

test('surfaces an error when unblocking fails and keeps the row', async () => {
  mockGetBlockedUsers.mockResolvedValue(blockedUsers)
  mockToggleBlock.mockRejectedValue(new Error('Rate limited'))
  const user = userEvent.setup()
  renderPage()

  await screen.findByText('alice')
  await user.click(screen.getAllByRole('button', { name: 'Unblock' })[0])

  expect(await screen.findByText('Rate limited')).toBeInTheDocument()
  expect(screen.getByText('alice')).toBeInTheDocument()
})

test('surfaces a load error', async () => {
  mockGetBlockedUsers.mockRejectedValue(new Error('Failed to load.'))
  renderPage()
  expect(await screen.findByText('Failed to load.')).toBeInTheDocument()
})
