import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, beforeEach, test, expect } from 'vitest'
import InterestsModal from './InterestsModal'
import {
  MAX_FREEFORM_INTEREST_LENGTH,
  MAX_FREEFORM_INTERESTS,
} from '../api/interestVocabulary'

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

test('blocks adding a freeform term over the length limit', async () => {
  const user = userEvent.setup()
  renderModal()
  await screen.findByRole('button', { name: 'Nature' })

  const input = screen.getByRole('textbox')
  const tooLong = 'a'.repeat(MAX_FREEFORM_INTEREST_LENGTH + 1)
  await user.type(input, tooLong)

  // Add stays disabled and the text is kept so the user can shorten it, rather
  // than being accepted here only to be dropped by the backend.
  const addButton = screen.getByRole('button', { name: 'Add' })
  expect(addButton).toBeDisabled()
  await user.click(addButton)
  expect(screen.queryByRole('button', { name: `Remove ${tooLong}` })).not.toBeInTheDocument()
  expect(input).toHaveValue(tooLong)

  // A term within the limit is still addable.
  await user.clear(input)
  await user.type(input, 'jazz')
  expect(screen.getByRole('button', { name: 'Add' })).toBeEnabled()
})

test('allows a comma list whose combined length exceeds the per-term limit', async () => {
  const user = userEvent.setup()
  const { onSaved } = renderModal()
  await screen.findByRole('button', { name: 'Nature' })

  // Each term is comfortably under the limit but the whole entry is well over
  // it. The limit is per term, so this must stay addable — gating on the raw
  // input length would wrongly block it.
  const half = 'a'.repeat(60)
  const other = 'b'.repeat(60)
  await user.type(screen.getByRole('textbox'), `${half}, ${other}`)
  expect(screen.getByRole('button', { name: 'Add' })).toBeEnabled()

  await user.click(screen.getByRole('button', { name: 'Add' }))
  await user.click(screen.getByRole('button', { name: 'Save' }))
  // 'hiking' is the prefilled term from getInterests.
  await waitFor(() =>
    expect(mockSet).toHaveBeenCalledWith({
      categories: ['nature'],
      freeform: ['hiking', half, other],
    }),
  )
  await waitFor(() => expect(onSaved).toHaveBeenCalled())
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

test('does not offer Save when the interests failed to load', async () => {
  const user = userEvent.setup()
  // A transient failure leaves the working state empty. Saving that would be a
  // full replace with nothing — wiping everything the user had stored.
  mockGet.mockRejectedValue(new Error('network'))
  renderModal()

  expect(await screen.findByRole('alert')).toHaveTextContent('Could not load your interests')
  const saveButton = screen.getByRole('button', { name: 'Save' })
  expect(saveButton).toBeDisabled()
  await user.click(saveButton)
  expect(mockSet).not.toHaveBeenCalled()
})

test('blocks adding once the freeform cap is reached, without eating the input', async () => {
  const user = userEvent.setup()
  // Start at the cap.
  const atCap = Array.from({ length: MAX_FREEFORM_INTERESTS }, (_, i) => `term${i}`)
  mockGet.mockResolvedValue({ categories: [], freeform: atCap })
  renderModal()
  await screen.findByRole('button', { name: 'Nature' })

  const input = screen.getByRole('textbox')
  await user.type(input, 'onemore')
  const addButton = screen.getByRole('button', { name: 'Add' })
  expect(addButton).toBeDisabled()
  expect(screen.getByRole('status')).toHaveTextContent(
    `maximum of ${MAX_FREEFORM_INTERESTS} interests`,
  )

  // Enter must not slip past the disabled button, and the text is kept.
  await user.type(input, '{Enter}')
  expect(input).toHaveValue('onemore')
  expect(screen.queryByRole('button', { name: 'Remove onemore' })).not.toBeInTheDocument()

  // Freeing a slot re-enables it.
  await user.click(screen.getByRole('button', { name: 'Remove term0' }))
  expect(screen.getByRole('button', { name: 'Add' })).toBeEnabled()
})

test('blocks a comma list that would overflow the cap rather than dropping part of it', async () => {
  const user = userEvent.setup()
  // One slot free, but two new terms entered: adding would silently drop one.
  const nearCap = Array.from({ length: MAX_FREEFORM_INTERESTS - 1 }, (_, i) => `term${i}`)
  mockGet.mockResolvedValue({ categories: [], freeform: nearCap })
  renderModal()
  await screen.findByRole('button', { name: 'Nature' })

  const input = screen.getByRole('textbox')
  await user.type(input, 'alpha, beta')
  expect(screen.getByRole('button', { name: 'Add' })).toBeDisabled()

  // One term fits.
  await user.clear(input)
  await user.type(input, 'alpha')
  expect(screen.getByRole('button', { name: 'Add' })).toBeEnabled()
})

test('re-typing an already-listed term at the cap is still allowed', async () => {
  const user = userEvent.setup()
  const atCap = Array.from({ length: MAX_FREEFORM_INTERESTS }, (_, i) => `term${i}`)
  mockGet.mockResolvedValue({ categories: [], freeform: atCap })
  renderModal()
  await screen.findByRole('button', { name: 'Nature' })

  // A duplicate consumes no room, so it must not be blocked by the cap.
  await user.type(screen.getByRole('textbox'), 'TERM0')
  expect(screen.getByRole('button', { name: 'Add' })).toBeEnabled()
})

test('re-seeds the chip selection from the response when the dialog stays open', async () => {
  const user = userEvent.setup()
  // One term is rejected (so the dialog stays open) and the server reports a
  // union that includes a bucket an accepted term mapped to.
  mockSet.mockResolvedValue({
    categories: ['nature', 'music'],
    freeform: {
      accepted: ['jazz'],
      rejected: [{ text: 'bad vibes', reason: 'did not meet our positivity guidelines' }],
    },
  })
  renderModal()
  await screen.findByRole('button', { name: 'Nature' })
  await user.click(screen.getByRole('button', { name: 'Save' }))

  // 'Music' was never ticked by hand — it came back in the stored union, so the
  // still-open dialog must show it selected, matching what a reopen would show.
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Music' })).toHaveAttribute('aria-pressed', 'true'),
  )
  expect(screen.getByRole('button', { name: 'Nature' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: 'Sports' })).toHaveAttribute('aria-pressed', 'false')
})
