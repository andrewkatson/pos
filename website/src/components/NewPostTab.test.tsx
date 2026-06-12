import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, beforeEach, afterEach, test, expect } from 'vitest'
import NewPostTab from './NewPostTab'

vi.mock('../api/client', () => ({
  apiClient: { createPost: vi.fn() },
}))

vi.mock('../api/s3Uploader', () => ({
  uploadImage: vi.fn(),
}))

import { apiClient } from '../api/client'
import { uploadImage } from '../api/s3Uploader'
const mockCreatePost = vi.mocked(apiClient.createPost)
const mockUploadImage = vi.mocked(uploadImage)

function makeFile() {
  return new File(['fake-bytes'], 'photo.png', { type: 'image/png' })
}

beforeEach(() => {
  mockCreatePost.mockReset()
  mockUploadImage.mockReset()
  // jsdom doesn't implement object URLs.
  vi.stubGlobal('URL', {
    ...URL,
    createObjectURL: vi.fn(() => 'blob:preview'),
    revokeObjectURL: vi.fn(),
  })
  vi.stubGlobal('localStorage', {
    getItem: vi.fn(() => 'user-123'),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('share button is disabled until a photo and caption are provided', async () => {
  render(<NewPostTab onPosted={() => {}} />)
  const button = screen.getByRole('button', { name: 'Share Post' })
  expect(button).toBeDisabled()

  await userEvent.upload(screen.getByLabelText('Choose a photo'), makeFile())
  expect(button).toBeDisabled()
  await userEvent.type(screen.getByLabelText('Caption'), 'great day')
  expect(button).toBeEnabled()
})

test('uploads the photo to S3 and creates the post on success', async () => {
  mockUploadImage.mockResolvedValue(
    'https://goodvibesonly-images.s3.us-east-2.amazonaws.com/user-123/abc.jpeg',
  )
  mockCreatePost.mockResolvedValue({ post_identifier: 'p1' })
  const onPosted = vi.fn()
  render(<NewPostTab onPosted={onPosted} />)

  const file = makeFile()
  await userEvent.upload(screen.getByLabelText('Choose a photo'), file)
  await userEvent.type(screen.getByLabelText('Caption'), 'great day')
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  await waitFor(() => expect(mockUploadImage).toHaveBeenCalledWith(file, 'user-123'))
  expect(mockCreatePost).toHaveBeenCalledWith({
    image_url: 'https://goodvibesonly-images.s3.us-east-2.amazonaws.com/user-123/abc.jpeg',
    caption: 'great day',
  })
  expect(await screen.findByText('Your post was shared successfully!')).toBeInTheDocument()
  expect(onPosted).toHaveBeenCalled()
})

test('shows an error when the upload fails', async () => {
  mockUploadImage.mockRejectedValue({ message: 'Upload failed' })
  render(<NewPostTab onPosted={() => {}} />)

  await userEvent.upload(screen.getByLabelText('Choose a photo'), makeFile())
  await userEvent.type(screen.getByLabelText('Caption'), 'great day')
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Upload failed')
  expect(mockCreatePost).not.toHaveBeenCalled()
})

test('shows an error when there is no signed-in user', async () => {
  vi.stubGlobal('localStorage', {
    getItem: vi.fn(() => null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  })
  render(<NewPostTab onPosted={() => {}} />)

  await userEvent.upload(screen.getByLabelText('Choose a photo'), makeFile())
  await userEvent.type(screen.getByLabelText('Caption'), 'great day')
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('You must be logged in to post.')
  expect(mockUploadImage).not.toHaveBeenCalled()
})
