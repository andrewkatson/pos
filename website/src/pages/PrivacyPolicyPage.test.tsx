import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import PrivacyPolicyPage from './PrivacyPolicyPage'
import { PRIVACY_POLICY_TEXT } from '../privacyPolicy'

function renderWithRouter(initialPath = '/privacy-policy') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/" element={<div>Landing page</div>} />
        <Route path="/privacy-policy" element={<PrivacyPolicyPage />} />
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
