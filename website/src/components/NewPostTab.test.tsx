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

/** The composer opens on the Text tab; photo flows start by switching (#520). */
async function switchToImagePost() {
  await userEvent.click(screen.getByRole('tab', { name: 'Image' }))
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
        comments_disabled: false,
}),
  )
  expect(mockUploadImage).not.toHaveBeenCalled()
  expect(await screen.findByText('Your post was shared successfully!')).toBeInTheDocument()
  expect(onPosted).toHaveBeenCalled()
})

test('disables the share button and shows the over-limit counter past 125 characters', async () => {
  render(<NewPostTab onPosted={() => {}} />)
  const button = screen.getByRole('button', { name: 'Share Post' })

  await switchToImagePost()
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
  await switchToImagePost()
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
    comments_disabled: false,
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
        comments_disabled: false,
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
        comments_disabled: false,
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

  await switchToImagePost()
  await userEvent.upload(screen.getByLabelText('Choose a photo'), makeFile())
  await userEvent.type(screen.getByLabelText('Caption'), 'maybe edgy')
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  expect(await screen.findByText(/hidden for now but you can appeal/i)).toBeInTheDocument()
})

test('hides the background-color control on the Image tab (#421, #520)', async () => {
  render(<NewPostTab onPosted={() => {}} />)

  // Visible on a text post.
  expect(screen.getByRole('button', { name: 'Mint' })).toBeInTheDocument()

  await switchToImagePost()

  // Gone on an image post — the color never shows there.
  expect(screen.queryByRole('button', { name: 'Mint' })).not.toBeInTheDocument()
})

test('sends the default background color for an image post even if one was picked on the Text tab (#421)', async () => {
  mockUploadImage.mockResolvedValue(
    'https://goodvibesonly-images.s3.us-east-2.amazonaws.com/user-123/abc.jpeg',
  )
  mockCreatePost.mockResolvedValue({ post_identifier: 'p1' })
  render(<NewPostTab onPosted={() => {}} />)

  await userEvent.type(screen.getByLabelText('Caption'), 'great day')
  await userEvent.click(screen.getByRole('button', { name: 'Mint' }))
  await switchToImagePost()
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

  await switchToImagePost()
  await userEvent.upload(screen.getByLabelText('Choose a photo'), makeFile())
  await userEvent.type(screen.getByLabelText('Caption'), 'great day')
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Upload failed')
  expect(mockCreatePost).not.toHaveBeenCalled()
})

test('the photo picker shows a + placeholder until a photo is chosen, then the image (#417)', async () => {
  render(<NewPostTab onPosted={() => {}} />)
  await switchToImagePost()

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
  await switchToImagePost()

  const input = screen.getByLabelText('Choose a photo') as HTMLInputElement
  await userEvent.upload(input, makeFile())

  // The preview appeared, but the input value is reset — otherwise the browser
  // skips onChange when the user re-picks the identical file via "Change photo".
  expect(screen.getByAltText('Selected post preview')).toBeInTheDocument()
  expect(input.value).toBe('')
})

test('a text post shows its formatting controls by default under "Text formatting" (#419, #520)', async () => {
  render(<NewPostTab onPosted={() => {}} />)

  const summary = screen.getByText('Text formatting')
  const details = summary.closest('details')
  // Expanded from the start: the caption is the whole post, so styling it is
  // the main event.
  expect(details).toHaveAttribute('open')
  // The font/color controls live inside the disclosure so it can still be hidden.
  expect(details).toContainElement(screen.getByLabelText('Font'))
  expect(details).toContainElement(screen.getByRole('button', { name: 'Mint' }))
})

test('an image post tucks the caption formatting behind a collapsed "Advanced options" (#520)', async () => {
  render(<NewPostTab onPosted={() => {}} />)
  await switchToImagePost()

  const summary = screen.getByText('Advanced options')
  const details = summary.closest('details')
  expect(details).not.toHaveAttribute('open')
  // The font still styles an image post's caption, so it stays available.
  expect(details).toContainElement(screen.getByLabelText('Font'))
  expect(screen.queryByText('Text formatting')).not.toBeInTheDocument()
})

test('switching tabs resets the formatting disclosure to each tab\'s default (#520)', async () => {
  render(<NewPostTab onPosted={() => {}} />)

  // Collapse it on the Text tab. (jsdom doesn't toggle <details> on a summary
  // click, so mimic the browser: flip `open` and emit the toggle event the
  // controlled disclosure listens for.)
  const textDetails = screen.getByText('Text formatting').closest('details') as HTMLDetailsElement
  textDetails.open = false
  fireEvent(textDetails, new Event('toggle'))
  expect(textDetails).not.toHaveAttribute('open')

  // ...an Image round-trip lands back on the Text default: expanded.
  await switchToImagePost()
  expect(screen.getByText('Advanced options').closest('details')).not.toHaveAttribute('open')
  await userEvent.click(screen.getByRole('tab', { name: 'Text' }))
  expect(screen.getByText('Text formatting').closest('details')).toHaveAttribute('open')
})

test('the preview shows the caption as a tile for a text-only post (#418)', async () => {
  render(<NewPostTab onPosted={() => {}} />)

  await userEvent.type(screen.getByLabelText('Caption'), 'a sunny thought')
  // A text-only post renders its caption as the tile (role="img" from CaptionTile).
  expect(screen.getByRole('img', { name: 'a sunny thought' })).toBeInTheDocument()
})

test("the preview applies the chosen font to an image post's caption (#450)", async () => {
  const { container } = render(<NewPostTab onPosted={() => {}} />)

  await switchToImagePost()
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

  await switchToImagePost()
  await userEvent.upload(screen.getByLabelText('Choose a photo'), makeFile())
  await userEvent.type(screen.getByLabelText('Caption'), 'great day')
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('You must be logged in to post.')
  expect(mockUploadImage).not.toHaveBeenCalled()
})

test('opens on the Text tab with no photo picker (#520)', () => {
  render(<NewPostTab onPosted={() => {}} />)

  expect(screen.getByRole('tab', { name: 'Text' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByRole('tab', { name: 'Image' })).toHaveAttribute('aria-selected', 'false')
  expect(screen.queryByLabelText('Choose a photo')).not.toBeInTheDocument()
})

test('an image post cannot be shared until a photo is picked (#520)', async () => {
  render(<NewPostTab onPosted={() => {}} />)
  await switchToImagePost()

  await userEvent.type(screen.getByLabelText('Caption'), 'needs a picture')
  const button = screen.getByRole('button', { name: 'Share Post' })
  expect(button).toBeDisabled()

  await userEvent.upload(screen.getByLabelText('Choose a photo'), makeFile())
  expect(button).toBeEnabled()
})

test('a photo picked on the Image tab is not sent with a Text post (#520)', async () => {
  mockCreatePost.mockResolvedValue({ post_identifier: 'p1' })
  render(<NewPostTab onPosted={() => {}} />)

  await switchToImagePost()
  await userEvent.upload(screen.getByLabelText('Choose a photo'), makeFile())
  await userEvent.click(screen.getByRole('tab', { name: 'Text' }))
  await userEvent.type(screen.getByLabelText('Caption'), 'just words')
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  await waitFor(() =>
    expect(mockCreatePost).toHaveBeenCalledWith({
      caption: 'just words',
      audience: 'public',
      caption_font: 'default',
      background_color: 'default',
        comments_disabled: false,
}),
  )
  expect(mockUploadImage).not.toHaveBeenCalled()
})

test("the Image tab previews the caption under a photo placeholder before a photo is picked (#520)", async () => {
  const { container } = render(<NewPostTab onPosted={() => {}} />)
  await switchToImagePost()

  // No photo yet: a placeholder holds the square and the caption line is
  // already there so the chosen font is visible.
  expect(screen.getByText('Your photo will appear here')).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText('Font'), 'serif')
  const caption = container.querySelector('.feed-post__caption')
  expect(caption).toHaveTextContent('Your caption will look like this.')
  expect(caption).toHaveClass('caption-font--serif')

  await userEvent.type(screen.getByLabelText('Caption'), 'a real caption')
  expect(container.querySelector('.feed-post__caption')).toHaveTextContent('a real caption')
})

test('a successful image post resets the composer to the Text tab (#520)', async () => {
  mockUploadImage.mockResolvedValue(
    'https://goodvibesonly-images.s3.us-east-2.amazonaws.com/user-123/abc.jpeg',
  )
  mockCreatePost.mockResolvedValue({ post_identifier: 'p1' })
  render(<NewPostTab onPosted={() => {}} />)

  await switchToImagePost()
  await userEvent.upload(screen.getByLabelText('Choose a photo'), makeFile())
  await userEvent.type(screen.getByLabelText('Caption'), 'great day')
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))
  await screen.findByText('Your post was shared successfully!')

  // Otherwise the next post would open on an empty Image tab with Share
  // disabled; instead it's a fresh Text composer with formatting expanded.
  expect(screen.getByRole('tab', { name: 'Text' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.queryByLabelText('Choose a photo')).not.toBeInTheDocument()
  expect(screen.getByText('Text formatting').closest('details')).toHaveAttribute('open')
})

test('sends comments_disabled when the author turns off commenting (#492)', async () => {
  mockCreatePost.mockResolvedValue({ post_identifier: 'p1' })
  render(<NewPostTab onPosted={() => {}} />)

  await userEvent.type(screen.getByLabelText('Caption'), 'quiet post')
  await userEvent.click(screen.getByLabelText('Turn off commenting on this post'))
  await userEvent.click(screen.getByRole('button', { name: 'Share Post' }))

  await waitFor(() =>
    expect(mockCreatePost).toHaveBeenCalledWith(
      expect.objectContaining({ caption: 'quiet post', comments_disabled: true }),
    ),
  )
})
