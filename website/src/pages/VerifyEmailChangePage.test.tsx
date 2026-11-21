import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router'
import { vi, beforeEach } from 'vitest'
import VerifyEmailChangePage from './VerifyEmailChangePage'

vi.mock('../api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return { ...actual, apiClient: { confirmEmailChange: vi.fn() } }
})

import { apiClient } from '../api/client'
const mockConfirm = vi.mocked(apiClient.confirmEmailChange)

const VALID_TOKEN = 'a'.repeat(43)

function renderPage(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/verify-email-change" element={<VerifyEmailChangePage />} />
        <Route path="/" element={<div>Landing page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockConfirm.mockReset()
})

test('confirms the token once and reports success', async () => {
  mockConfirm.mockResolvedValueOnce({ message: 'Email changed' })
  renderPage(`/verify-email-change?token=${VALID_TOKEN}`)

  expect(await screen.findByText(/has been changed/)).toBeInTheDocument()
  expect(mockConfirm).toHaveBeenCalledWith({ verification_token: VALID_TOKEN })
  expect(mockConfirm).toHaveBeenCalledTimes(1)

  await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
  expect(screen.getByText('Landing page')).toBeInTheDocument()
})

test('an address taken since the request shows our own copy', async () => {
  mockConfirm.mockRejectedValueOnce({ message: 'email_in_use' })
  renderPage(`/verify-email-change?token=${VALID_TOKEN}`)
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Another account already uses that email address.',
  )
  // An error can't prove the change didn't happen (a reused link, a lost
  // response), so the page points at Settings rather than promising either way.
  expect(screen.getByText(/Check Settings to see which email your account uses/)).toBeInTheDocument()
})

test('an expired link shows the backend message', async () => {
  mockConfirm.mockRejectedValueOnce({ message: 'Invalid or expired verification token' })
  renderPage(`/verify-email-change?token=${VALID_TOKEN}`)
  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid or expired verification token')
})

test('a link without a token asks for the emailed link and sends nothing', () => {
  renderPage('/verify-email-change')
  expect(screen.getByText(/missing its token/)).toBeInTheDocument()
  expect(mockConfirm).not.toHaveBeenCalled()
})
