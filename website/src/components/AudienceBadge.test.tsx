import { render, screen } from '@testing-library/react'
import { test, expect } from 'vitest'
import AudienceBadge from './AudienceBadge'
import type { PostAudience } from '../api/types'

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

test('an unknown tier falls back to public, including prototype names', () => {
  // A newer backend tier this client doesn't know, and a string that would
  // pass a plain `in` check by matching Object.prototype.
  render(
    <>
      <AudienceBadge audience={'coworkers' as PostAudience} />
      <AudienceBadge audience={'toString' as PostAudience} />
    </>,
  )
  const badges = screen.getAllByLabelText('Visible to anyone')
  expect(badges).toHaveLength(2)
  for (const badge of badges) expect(badge).toHaveAttribute('data-audience', 'public')
})

test('compact mode drops the visible label but keeps the accessible one', () => {
  render(<AudienceBadge audience="family" compact />)
  const badge = screen.getByLabelText('Visible to family only')
  expect(badge).not.toHaveTextContent('Family')
  expect(badge).toHaveAttribute('title', 'Visible to family only')
  expect(badge).toHaveClass('audience-badge--compact')
})
