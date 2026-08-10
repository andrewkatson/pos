import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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

test('share button is enabled by a caption alone — the photo is optional (#307)', async () => {
  render(<NewPostTab onPosted={() => {}} />)
  const button = screen.getByRole('button', { name: 'Share Post' })
  expect(button).toBeDisabled()

  await userEvent.type(screen.getByLabelText('Caption'), 'great day')
  expect(button).toBeEnabled()
})

test('creates a text-only post without uploading to S3 (#307)', async () => {
  mockCreatePost.mockResolvedValue({ post_identifier: 'p1' })
  const onPosted = vi.fn()
  render(<NewPostTab onPosted={onPosted} />)

  await userEvent.type(screen.getByLabelText('Caption'), 'words only today')
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  await waitFor(() =>
    expect(mockCreatePost).toHaveBeenCalledWith({
      caption: 'words only today',
      audience: 'public',
      caption_font: 'default',
      background_color: 'default',
    }),
  )
  expect(mockUploadImage).not.toHaveBeenCalled()
  expect(await screen.findByText('Your post was shared successfully!')).toBeInTheDocument()
  expect(onPosted).toHaveBeenCalled()
})

test('disables the share button and shows the over-limit counter past 125 characters', async () => {
  render(<NewPostTab onPosted={() => {}} />)
  const button = screen.getByRole('button', { name: 'Share Post' })

  await userEvent.upload(screen.getByLabelText('Choose a photo'), makeFile())
  // fireEvent.change sets the value directly, avoiding 126 simulated keystrokes.
  fireEvent.change(screen.getByLabelText('Caption'), { target: { value: 'a'.repeat(126) } })

  expect(button).toBeDisabled()
  expect(screen.getByText('1 over the 125 character limit')).toBeInTheDocument()
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

  await waitFor(() => expect(mockUploadImage).toHaveBeenCalledWith(file))
  expect(mockCreatePost).toHaveBeenCalledWith({
    image_url: 'https://goodvibesonly-images.s3.us-east-2.amazonaws.com/user-123/abc.jpeg',
    caption: 'great day',
    audience: 'public',
    caption_font: 'default',
    background_color: 'default',
  })
  expect(await screen.findByText('Your post was shared successfully!')).toBeInTheDocument()
  expect(onPosted).toHaveBeenCalled()
})

test('sends the chosen audience with the post (#392)', async () => {
  mockCreatePost.mockResolvedValue({ post_identifier: 'p1' })
  render(<NewPostTab onPosted={() => {}} />)

  await userEvent.type(screen.getByLabelText('Caption'), 'family news')
  await userEvent.selectOptions(screen.getByLabelText('Audience'), 'family')
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  await waitFor(() =>
    expect(mockCreatePost).toHaveBeenCalledWith({
      caption: 'family news',
      audience: 'family',
      caption_font: 'default',
      background_color: 'default',
    }),
  )
})

test('sends the chosen caption font and background color (#318)', async () => {
  mockCreatePost.mockResolvedValue({ post_identifier: 'p1' })
  render(<NewPostTab onPosted={() => {}} />)

  await userEvent.type(screen.getByLabelText('Caption'), 'styled words')
  await userEvent.selectOptions(screen.getByLabelText('Font'), 'serif')
  await userEvent.click(screen.getByRole('button', { name: 'Mint' }))
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  await waitFor(() =>
    expect(mockCreatePost).toHaveBeenCalledWith({
      caption: 'styled words',
      audience: 'public',
      caption_font: 'serif',
      background_color: 'mint',
    }),
  )
})

test('shows the review-in-progress message for a pending post (#282)', async () => {
  mockCreatePost.mockResolvedValue({
    post_identifier: 'p1',
    status: 'pending',
    hidden: true,
    hidden_reason: 'pending_classification',
    message: 'Your post is being reviewed and will be visible to others once it is approved.',
  })
  const onPosted = vi.fn()
  render(<NewPostTab onPosted={onPosted} />)

  await userEvent.type(screen.getByLabelText('Caption'), 'great day')
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  expect(await screen.findByText(/being reviewed/i)).toBeInTheDocument()
  expect(onPosted).toHaveBeenCalled()
})

test('shows the appeal message when the post is hidden pending appeal', async () => {
  mockUploadImage.mockResolvedValue(
    'https://goodvibesonly-images.s3.us-east-2.amazonaws.com/user-123/abc.jpeg',
  )
  mockCreatePost.mockResolvedValue({
    post_identifier: 'p1',
    hidden: true,
    hidden_reason: 'classifier',
    message: 'Your post did not pass automated review. It is hidden for now but you can appeal the decision.',
  })
  render(<NewPostTab onPosted={() => {}} />)

  await userEvent.upload(screen.getByLabelText('Choose a photo'), makeFile())
  await userEvent.type(screen.getByLabelText('Caption'), 'maybe edgy')
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  expect(await screen.findByText(/hidden for now but you can appeal/i)).toBeInTheDocument()
})

test('hides the background-color control once a photo is selected (#421)', async () => {
  render(<NewPostTab onPosted={() => {}} />)

  // The color swatches live behind the Advanced options disclosure (#419), so
  // open it first to match the real user flow.
  await userEvent.click(screen.getByText('Advanced options'))

  // Visible on a text-only post.
  expect(screen.getByRole('button', { name: 'Mint' })).toBeInTheDocument()

  await userEvent.upload(screen.getByLabelText('Choose a photo'), makeFile())

  // Gone once a photo is attached — the color never shows on an image post.
  expect(screen.queryByRole('button', { name: 'Mint' })).not.toBeInTheDocument()
})

test('sends the default background color even if one was picked before adding a photo (#421)', async () => {
  mockUploadImage.mockResolvedValue(
    'https://goodvibesonly-images.s3.us-east-2.amazonaws.com/user-123/abc.jpeg',
  )
  mockCreatePost.mockResolvedValue({ post_identifier: 'p1' })
  render(<NewPostTab onPosted={() => {}} />)

  // The color swatches live behind the Advanced options disclosure (#419).
  await userEvent.click(screen.getByText('Advanced options'))
  await userEvent.type(screen.getByLabelText('Caption'), 'great day')
  await userEvent.click(screen.getByRole('button', { name: 'Mint' }))
  await userEvent.upload(screen.getByLabelText('Choose a photo'), makeFile())
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  await waitFor(() =>
    expect(mockCreatePost).toHaveBeenCalledWith(
      expect.objectContaining({ background_color: 'default' }),
    ),
  )
})

test('keeps the share button visible with a processing label while submitting (#306)', async () => {
  let resolveCreate: () => void = () => {}
  mockCreatePost.mockReturnValue(
    new Promise(resolve => {
      resolveCreate = () => resolve({ post_identifier: 'p1' })
    }),
  )
  render(<NewPostTab onPosted={() => {}} />)

  await userEvent.type(screen.getByLabelText('Caption'), 'great day')
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  const processing = await screen.findByRole('button', { name: 'Processing…' })
  expect(processing).toBeInTheDocument()
  expect(processing).toBeDisabled()

  resolveCreate()
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Share Post' })).toBeInTheDocument(),
  )
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

test('the photo picker shows a + placeholder until a photo is chosen, then the image (#417)', async () => {
  render(<NewPostTab onPosted={() => {}} />)

  // Before a photo: the picker invites adding one and shows no image.
  const picker = screen.getByRole('button', { name: 'Add a photo' })
  expect(picker).toBeInTheDocument()
  expect(screen.queryByAltText('Selected post preview')).not.toBeInTheDocument()

  await userEvent.upload(screen.getByLabelText('Choose a photo'), makeFile())

  // After: the picker becomes the image target ("Change photo") and shows it.
  expect(screen.getByRole('button', { name: 'Change photo' })).toBeInTheDocument()
  expect(screen.getByAltText('Selected post preview')).toBeInTheDocument()
})

test('the file input is cleared after a pick so the same file can be re-selected', async () => {
  render(<NewPostTab onPosted={() => {}} />)

  const input = screen.getByLabelText('Choose a photo') as HTMLInputElement
  await userEvent.upload(input, makeFile())

  // The preview appeared, but the input value is reset — otherwise the browser
  // skips onChange when the user re-picks the identical file via "Change photo".
  expect(screen.getByAltText('Selected post preview')).toBeInTheDocument()
  expect(input.value).toBe('')
})

test('style settings live behind an Advanced options disclosure (#419)', async () => {
  render(<NewPostTab onPosted={() => {}} />)

  const summary = screen.getByText('Advanced options')
  expect(summary).toBeInTheDocument()
  // The font/color controls live inside the disclosure.
  expect(summary.closest('details')).toContainElement(screen.getByLabelText('Font'))
  expect(summary.closest('details')).toContainElement(
    screen.getByRole('button', { name: 'Mint' }),
  )
})

test('the preview shows the caption as a tile for a text-only post (#418)', async () => {
  render(<NewPostTab onPosted={() => {}} />)

  await userEvent.type(screen.getByLabelText('Caption'), 'a sunny thought')
  // A text-only post renders its caption as the tile (role="img" from CaptionTile).
  expect(screen.getByRole('img', { name: 'a sunny thought' })).toBeInTheDocument()
})

test("the preview applies the chosen font to an image post's caption (#450)", async () => {
  const { container } = render(<NewPostTab onPosted={() => {}} />)

  await userEvent.upload(screen.getByLabelText('Choose a photo'), makeFile())
  await userEvent.type(screen.getByLabelText('Caption'), 'a sunny thought')
  await userEvent.selectOptions(screen.getByLabelText('Font'), 'serif')

  // With a photo attached the caption sits under the image, exactly as the feed
  // renders it — and carries the chosen font there too.
  expect(container.querySelector('.feed-post__caption')).toHaveClass('caption-font--serif')
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
