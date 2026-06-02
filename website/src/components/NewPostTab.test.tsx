import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, beforeEach, test, expect } from 'vitest'
import NewPostTab from './NewPostTab'

vi.mock('../api/client', () => ({
  apiClient: { createPost: vi.fn() },
}))

import { apiClient } from '../api/client'
const mockCreatePost = vi.mocked(apiClient.createPost)

beforeEach(() => {
  mockCreatePost.mockReset()
})

test('share button is disabled until both fields are filled', async () => {
  render(<NewPostTab onPosted={() => {}} />)
  const button = screen.getByRole('button', { name: 'Share Post' })
  expect(button).toBeDisabled()

  await userEvent.type(screen.getByLabelText('Image URL'), 'http://img/1.jpg')
  expect(button).toBeDisabled()
  await userEvent.type(screen.getByLabelText('Caption'), 'great day')
  expect(button).toBeEnabled()
})

test('creates a post and notifies the parent on success', async () => {
  mockCreatePost.mockResolvedValue({ post_identifier: 'p1' })
  const onPosted = vi.fn()
  render(<NewPostTab onPosted={onPosted} />)

  await userEvent.type(screen.getByLabelText('Image URL'), 'http://img/1.jpg')
  await userEvent.type(screen.getByLabelText('Caption'), 'great day')
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  expect(mockCreatePost).toHaveBeenCalledWith({
    image_url: 'http://img/1.jpg',
    caption: 'great day',
  })
  expect(await screen.findByText('Your post was shared successfully!')).toBeInTheDocument()
  expect(onPosted).toHaveBeenCalled()
})

test('shows an error banner when the post is rejected', async () => {
  mockCreatePost.mockRejectedValue({ message: 'Text is not positive' })
  render(<NewPostTab onPosted={() => {}} />)

  await userEvent.type(screen.getByLabelText('Image URL'), 'http://img/1.jpg')
  await userEvent.type(screen.getByLabelText('Caption'), 'negative vibes')
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Text is not positive')
})
