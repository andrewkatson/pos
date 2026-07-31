import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, beforeEach, test, expect } from 'vitest'
import InterestsModal from './InterestsModal'

vi.mock('../api/client', () => ({
  apiClient: {
    getInterestOptions: vi.fn(),
    getInterests: vi.fn(),
    setInterests: vi.fn(),
  },
}))

import { apiClient } from '../api/client'
const mockOptions = vi.mocked(apiClient.getInterestOptions)
const mockGet = vi.mocked(apiClient.getInterests)
const mockSet = vi.mocked(apiClient.setInterests)

const OPTIONS = {
  options: [
    { slug: 'nature', name: 'Nature' },
    { slug: 'music', name: 'Music' },
    { slug: 'sports', name: 'Sports' },
  ],
}

beforeEach(() => {
  mockOptions.mockReset().mockResolvedValue(OPTIONS)
  mockGet.mockReset().mockResolvedValue({ categories: ['nature'], freeform: ['hiking'] })
  mockSet.mockReset().mockResolvedValue({
    categories: ['nature'],
    freeform: { accepted: [], rejected: [] },
    message: 'Your interests have been updated.',
  })
})

function renderModal() {
  const onClose = vi.fn()
  const onSaved = vi.fn()
  render(<InterestsModal onClose={onClose} onSaved={onSaved} />)
  return { onClose, onSaved }
}

test('prefills the picker from the current selection', async () => {
  renderModal()
  // Preset chip reflects the current selection.
  const nature = await screen.findByRole('button', { name: 'Nature' })
  expect(nature).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: 'Music' })).toHaveAttribute('aria-pressed', 'false')
  // Existing freeform term shows as a removable pill.
  expect(screen.getByText('hiking')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Remove hiking' })).toBeInTheDocument()
})

test('toggles a bucket, removes a freeform term, adds one, and saves the full set', async () => {
  const user = userEvent.setup()
  const { onSaved } = renderModal()

  await screen.findByRole('button', { name: 'Nature' })
  // Select Music, remove the prefilled "hiking", add "jazz".
  await user.click(screen.getByRole('button', { name: 'Music' }))
  await user.click(screen.getByRole('button', { name: 'Remove hiking' }))
  await user.type(screen.getByRole('textbox'), 'jazz')
  await user.click(screen.getByRole('button', { name: 'Add' }))
  await user.click(screen.getByRole('button', { name: 'Save' }))

  await waitFor(() => expect(mockSet).toHaveBeenCalledTimes(1))
  expect(mockSet).toHaveBeenCalledWith({
    categories: ['nature', 'music'],
    freeform: ['jazz'],
  })
  await waitFor(() => expect(onSaved).toHaveBeenCalledWith('Your interests have been updated.'))
})

test('deselecting a bucket removes it from the saved set', async () => {
  const user = userEvent.setup()
  renderModal()
  const nature = await screen.findByRole('button', { name: 'Nature' })
  await user.click(nature) // deselect the prefilled bucket
  await user.click(screen.getByRole('button', { name: 'Remove hiking' }))
  await user.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(mockSet).toHaveBeenCalledWith({ categories: [], freeform: [] }))
})

test('shows rejected freeform terms and keeps the dialog open', async () => {
  const user = userEvent.setup()
  mockSet.mockResolvedValue({
    categories: ['nature'],
    freeform: {
      accepted: [],
      rejected: [{ text: 'bad vibes', reason: 'did not meet our positivity guidelines' }],
    },
  })
  const { onSaved } = renderModal()
  await screen.findByRole('button', { name: 'Nature' })
  await user.type(screen.getByRole('textbox'), 'bad vibes')
  await user.click(screen.getByRole('button', { name: 'Add' }))
  await user.click(screen.getByRole('button', { name: 'Save' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('bad vibes')
  expect(onSaved).not.toHaveBeenCalled()
})
