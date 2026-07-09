import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import LandingPage from './LandingPage'

function renderWithRouter(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<div>Login page</div>} />
        <Route path="/register" element={<div>Register page</div>} />
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
