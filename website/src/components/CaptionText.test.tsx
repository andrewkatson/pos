import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { test, expect } from 'vitest'
import { CaptionText } from './CaptionText'

function renderCaption(caption: string) {
  return render(
    <MemoryRouter initialEntries={['/post/1']}>
      <Routes>
        <Route path="/post/1" element={<CaptionText caption={caption} />} />
        <Route path="/tags/:tag" element={<div>Tag feed</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

test('renders plain text with no tag buttons', () => {
  renderCaption('a plain caption')
  expect(screen.getByText('a plain caption')).toBeInTheDocument()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

test('renders a #tag as a button and navigates to its feed', async () => {
  renderCaption('lovely #sunset tonight')

  const tagButton = screen.getByRole('button', { name: '#sunset' })
  expect(tagButton).toBeInTheDocument()

  await userEvent.click(tagButton)
  expect(screen.getByText('Tag feed')).toBeInTheDocument()
})

test('links the normalized (lowercased) tag even when typed mixed-case', () => {
  renderCaption('#SunSet')
  // The displayed text keeps the original casing...
  const tagButton = screen.getByRole('button', { name: '#SunSet' })
  expect(tagButton).toBeInTheDocument()
})
