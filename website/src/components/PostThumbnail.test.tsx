import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PostThumbnail from './PostThumbnail'

// A valid canonical BlurHash (the Wolt example string).
const BLURHASH = 'LEHV6nWB2yk8pyo0adR*.7kCMdnj'

const basePost = {
  image_url: 'http://compressed/1.jpg',
  original_image_url: 'http://original/1.jpg',
  image_blurhash: BLURHASH,
  caption: 'hi',
}

describe('PostThumbnail', () => {
  it('shows the BlurHash placeholder until the image loads, then removes it (#387)', () => {
    const { container } = render(<PostThumbnail post={basePost} />)

    // The blurred preview canvas sits behind the image while it loads.
    expect(container.querySelector('canvas.post-thumbnail__blur')).not.toBeNull()

    fireEvent.load(screen.getByAltText('hi'))

    // Once the image paints, the placeholder is gone.
    expect(container.querySelector('canvas.post-thumbnail__blur')).toBeNull()
  })

  it('omits the placeholder when the post has no BlurHash', () => {
    const { container } = render(
      <PostThumbnail post={{ ...basePost, image_blurhash: null }} />,
    )
    expect(container.querySelector('canvas.post-thumbnail__blur')).toBeNull()
    expect(screen.getByAltText('hi')).toBeInTheDocument()
  })

  it('falls back to the original image when the compressed one fails (#252/#254)', () => {
    render(<PostThumbnail post={basePost} />)
    const img = screen.getByAltText('hi')
    expect(img.getAttribute('src')).toBe('http://compressed/1.jpg')

    fireEvent.error(img)
    expect(img.getAttribute('src')).toBe('http://original/1.jpg')

    // The flag flips at most once: a failing original leaves it there, no loop.
    fireEvent.error(img)
    expect(img.getAttribute('src')).toBe('http://original/1.jpg')
  })

  it('renders a caption tile (no image) for a text-only post (#307)', () => {
    const { container } = render(
      <PostThumbnail post={{ ...basePost, image_url: null }} />,
    )
    expect(screen.queryByAltText('hi')).toBeNull()
    expect(container.querySelector('canvas.post-thumbnail__blur')).toBeNull()
  })
})
