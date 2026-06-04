import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import SettingsTab from './SettingsTab'

vi.mock('../api/client', () => ({
  apiClient: {
    logout: vi.fn(),
    deleteAccount: vi.fn(),
    verifyIdentity: vi.fn(),
    setToken: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockLogout = vi.mocked(apiClient.logout)
const mockDelete = vi.mocked(apiClient.deleteAccount)
const mockVerify = vi.mocked(apiClient.verifyIdentity)

function renderTab() {
  return render(
    <MemoryRouter initialEntries={['/home']}>
      <Routes>
        <Route path="/home" element={<SettingsTab />} />
        <Route path="/" element={<div>Landing page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockLogout.mockReset().mockResolvedValue({ message: 'ok' })
  mockDelete.mockReset().mockResolvedValue({ message: 'ok' })
  mockVerify.mockReset().mockResolvedValue({ message: 'ok' })
  vi.stubGlobal('localStorage', {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('logout requires confirmation then signs out', async () => {
  renderTab()
  await userEvent.click(screen.getByRole('button', { name: 'Logout' }))
  // Confirm dialog appears.
  await userEvent.click(
    screen.getByRole('dialog', { name: /log out/i }).querySelector('.modal__confirm')!,
  )
  expect(mockLogout).toHaveBeenCalled()
  expect(await screen.findByText('Landing page')).toBeInTheDocument()
})

test('delete account requires confirmation then deletes', async () => {
  renderTab()
  await userEvent.click(screen.getByRole('button', { name: 'Delete Account' }))
  await userEvent.click(
    screen.getByRole('dialog', { name: /delete your account/i }).querySelector('.modal__confirm')!,
  )
  expect(mockDelete).toHaveBeenCalled()
  expect(await screen.findByText('Landing page')).toBeInTheDocument()
})

test('verify identity submits the date of birth', async () => {
  renderTab()
  await userEvent.click(screen.getByRole('button', { name: 'Verify Identity' }))
  await userEvent.type(screen.getByLabelText('Date of birth'), '1990-01-01')
  await userEvent.click(screen.getByRole('button', { name: 'Verify' }))
  expect(mockVerify).toHaveBeenCalledWith('1990-01-01')
  expect(await screen.findByText('Identity verified successfully!')).toBeInTheDocument()
})

test('privacy policy can be shown', async () => {
  renderTab()
  await userEvent.click(screen.getByRole('button', { name: 'Privacy Policy' }))
  expect(screen.getByRole('dialog', { name: 'Privacy Policy' })).toBeInTheDocument()
})
