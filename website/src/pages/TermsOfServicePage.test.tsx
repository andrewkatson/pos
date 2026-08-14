import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router'
import TermsOfServicePage from './TermsOfServicePage'
import { TERMS_OF_SERVICE_SECTIONS } from '../termsOfService'

function renderWithRouter(initialPath = '/terms-of-service') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/" element={<div>Landing page</div>} />
        <Route path="/terms-of-service" element={<TermsOfServicePage />} />
        <Route path="/privacy-policy" element={<div>Privacy policy page</div>} />
        <Route path="/delete-account" element={<div>Delete account page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

test('renders every section without requiring auth', () => {
  renderWithRouter()

  expect(screen.getByRole('heading', { level: 1, name: 'Terms of Service' })).toBeInTheDocument()
  for (const section of TERMS_OF_SERVICE_SECTIONS) {
    expect(screen.getByRole('heading', { level: 2, name: section.heading })).toBeInTheDocument()
    expect(screen.getByText(section.body)).toBeInTheDocument()
  }
})

test('covers what Google sign-in shares, since the OAuth consent screen links here', () => {
  renderWithRouter()

  expect(screen.getByRole('heading', { name: 'Signing in with Google' })).toBeInTheDocument()
})

test('logo links back to the landing page', () => {
  renderWithRouter()

  const homeLink = screen.getByRole('link', { name: 'Good Vibes Only smiley logo' })
  expect(homeLink).toHaveAttribute('href', '/')
})

test('links to the privacy policy and the deletion page', () => {
  renderWithRouter()

  expect(screen.getByRole('link', { name: 'Privacy Policy' })).toHaveAttribute(
    'href',
    '/privacy-policy',
  )
  expect(screen.getByRole('link', { name: 'account & data deletion page' })).toHaveAttribute(
    'href',
    '/delete-account',
  )
})
