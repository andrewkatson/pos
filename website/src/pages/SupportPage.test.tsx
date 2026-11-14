import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router'
import SupportPage from './SupportPage'
import { SUPPORT_EMAIL, SUPPORT_SECTIONS } from '../support'

function renderWithRouter(initialPath = '/support') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/" element={<div>Landing page</div>} />
        <Route path="/support" element={<SupportPage />} />
        <Route path="/privacy-policy" element={<div>Privacy policy page</div>} />
        <Route path="/terms-of-service" element={<div>Terms of service page</div>} />
        <Route path="/delete-account" element={<div>Delete account page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

// The App Store Support URL points at this page, and Apple opens it signed
// out — as does a suspended user who cannot log in at all.
test('renders the support heading and contact address without requiring auth', () => {
  renderWithRouter()

  expect(screen.getByRole('heading', { name: 'Support' })).toBeInTheDocument()
  const email = screen.getByRole('link', { name: SUPPORT_EMAIL })
  expect(email).toHaveAttribute('href', `mailto:${SUPPORT_EMAIL}`)
})

test('renders every support section', () => {
  renderWithRouter()

  for (const section of SUPPORT_SECTIONS) {
    expect(screen.getByRole('heading', { name: section.heading })).toBeInTheDocument()
    expect(screen.getByText(section.body)).toBeInTheDocument()
  }
})

test('logo links back to the landing page', () => {
  renderWithRouter()

  const homeLink = screen.getByRole('link', { name: 'Good Vibes Only smiley logo' })
  expect(homeLink).toHaveAttribute('href', '/')
})

test('links to the privacy policy, terms, and account deletion', () => {
  renderWithRouter()

  expect(screen.getByRole('link', { name: 'Privacy Policy' })).toHaveAttribute(
    'href',
    '/privacy-policy',
  )
  expect(screen.getByRole('link', { name: 'Terms of Service' })).toHaveAttribute(
    'href',
    '/terms-of-service',
  )
  expect(screen.getByRole('link', { name: 'account & data deletion page' })).toHaveAttribute(
    'href',
    '/delete-account',
  )
})
