import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router'
import PrivacyPolicyPage from './PrivacyPolicyPage'
import { PRIVACY_POLICY_TEXT } from '../privacyPolicy'

function renderWithRouter(initialPath = '/privacy-policy') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/" element={<div>Landing page</div>} />
        <Route path="/privacy-policy" element={<PrivacyPolicyPage />} />
        <Route path="/delete-account" element={<div>Delete account page</div>} />
        <Route path="/terms-of-service" element={<div>Terms of service page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

test('renders the privacy policy heading and text without requiring auth', () => {
  renderWithRouter()

  expect(screen.getByRole('heading', { name: 'Privacy Policy' })).toBeInTheDocument()
  expect(screen.getByText(PRIVACY_POLICY_TEXT)).toBeInTheDocument()
})

test('logo links back to the landing page', () => {
  renderWithRouter()

  const homeLink = screen.getByRole('link', { name: 'Good Vibes Only smiley logo' })
  expect(homeLink).toHaveAttribute('href', '/')
})

test('links to the account & data deletion page', () => {
  renderWithRouter()

  const deletionLink = screen.getByRole('link', { name: 'account & data deletion page' })
  expect(deletionLink).toHaveAttribute('href', '/delete-account')
})

test('links to the terms of service', () => {
  renderWithRouter()

  const termsLink = screen.getByRole('link', { name: 'Terms of Service' })
  expect(termsLink).toHaveAttribute('href', '/terms-of-service')
})
