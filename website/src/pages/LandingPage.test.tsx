import { render, screen } from '@testing-library/react'
import LandingPage from './LandingPage'

test('shows the title, logo, and auth buttons', () => {
  render(<LandingPage />)

  expect(screen.getByRole('heading', { name: 'Good Vibes Only' })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: /smiley logo/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Sign up' })).toBeInTheDocument()
})
