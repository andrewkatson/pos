import { render, screen } from '@testing-library/react'
import { test, expect } from 'vitest'
import AudienceBadge from './AudienceBadge'

// Who can see a post or comment, shown to its author (issue #518).

test('names each audience tier and who it admits', () => {
  render(
    <>
      <AudienceBadge audience="public" />
      <AudienceBadge audience="following" />
      <AudienceBadge audience="friends" />
      <AudienceBadge audience="family" />
    </>,
  )
  expect(screen.getByLabelText('Visible to anyone')).toHaveTextContent('Public')
  expect(screen.getByLabelText('Visible to people you follow')).toHaveTextContent('Following')
  expect(screen.getByLabelText('Visible to friends and family')).toHaveTextContent('Friends')
  expect(screen.getByLabelText('Visible to family only')).toHaveTextContent('Family')
})

test('treats a missing audience as public, like the backend does', () => {
  render(<AudienceBadge />)
  expect(screen.getByLabelText('Visible to anyone')).toHaveAttribute('data-audience', 'public')
})

test('compact mode drops the visible label but keeps the accessible one', () => {
  render(<AudienceBadge audience="family" compact />)
  const badge = screen.getByLabelText('Visible to family only')
  expect(badge).not.toHaveTextContent('Family')
  expect(badge).toHaveAttribute('title', 'Visible to family only')
  expect(badge).toHaveClass('audience-badge--compact')
})
