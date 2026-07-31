import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router'
import { vi, beforeEach, test, expect } from 'vitest'
import LandingPage from './LandingPage'

// isAuthenticated is checked on mount to bounce an already-remembered session
// into the app; default it to false so the marketing landing page renders.
vi.mock('../api/client', () => ({
  apiClient: { isAuthenticated: vi.fn(() => false) },
}))

import { apiClient } from '../api/client'
const mockIsAuthenticated = vi.mocked(apiClient.isAuthenticated)

beforeEach(() => {
  mockIsAuthenticated.mockReset().mockReturnValue(false)
})

function renderWithRouter(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<div>Login page</div>} />
        <Route path="/register" element={<div>Register page</div>} />
        <Route path="/home" element={<div>Home page</div>} />
        <Route path="/privacy-policy" element={<div>Privacy policy page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

test('shows the title, logo, and auth buttons', () => {
  renderWithRouter()

  expect(screen.getByRole('heading', { name: 'Good Vibes Only' })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: /smiley logo/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Sign up' })).toBeInTheDocument()
})

test('Login button navigates to /login', async () => {
  renderWithRouter()
  await userEvent.click(screen.getByRole('button', { name: 'Login' }))
  expect(screen.getByText('Login page')).toBeInTheDocument()
})

test('Sign up button navigates to /register', async () => {
  renderWithRouter()
  await userEvent.click(screen.getByRole('button', { name: 'Sign up' }))
  expect(screen.getByText('Register page')).toBeInTheDocument()
})

test('Privacy Policy link navigates to /privacy-policy', async () => {
  renderWithRouter()
  await userEvent.click(screen.getByRole('link', { name: 'Privacy Policy' }))
  expect(screen.getByText('Privacy policy page')).toBeInTheDocument()
})

test('sends an already-remembered session straight into the app', async () => {
  // A returning "Remember Me" user has their session restored before render
  // (main.tsx); they must skip this logged-out screen, not be asked to sign in
  // (and clear 2FA) again (issue #411).
  mockIsAuthenticated.mockReturnValue(true)
  renderWithRouter()
  expect(await screen.findByText('Home page')).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Good Vibes Only' })).not.toBeInTheDocument()
})
