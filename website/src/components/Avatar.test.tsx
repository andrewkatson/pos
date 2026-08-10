import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Avatar from './Avatar'

// A valid canonical BlurHash (the Wolt example string).
const BLURHASH = 'LEHV6nWB2yk8pyo0adR*.7kCMdnj'

const blur = (container: HTMLElement) => container.querySelector('canvas.avatar__blur')
const photo = (container: HTMLElement) => container.querySelector('img.avatar__img')

describe('Avatar', () => {
  it('shows the BlurHash placeholder until the photo loads, then removes it (#460)', () => {
    const { container } = render(<Avatar src="http://compressed/a.jpg" blurhash={BLURHASH} />)

    expect(blur(container)).not.toBeNull()

    fireEvent.load(photo(container)!)

    expect(blur(container)).toBeNull()
  })

  it('leaves the blurred preview in place when the photo never loads', () => {
    const { container } = render(
      <Avatar src="http://compressed/a.jpg" originalSrc="http://original/a.jpg" blurhash={BLURHASH} />,
    )

    // Falling back to the original keeps the blur: the avatar is still loading.
    fireEvent.error(photo(container)!)
    expect(photo(container)!.getAttribute('src')).toBe('http://original/a.jpg')
    expect(blur(container)).not.toBeNull()

    // And once the original fails too, the blur stays as the final fallback
    // rather than dropping to the glyph — it's a truer stand-in for the photo.
    fireEvent.error(photo(container)!)
    expect(photo(container)).toBeNull()
    expect(blur(container)).not.toBeNull()
    expect(container.querySelector('.avatar')?.textContent).not.toContain('◍')
  })

  it('omits the placeholder when the user has no BlurHash', () => {
    const { container } = render(<Avatar src="http://compressed/a.jpg" blurhash={null} />)
    expect(blur(container)).toBeNull()
    expect(photo(container)).not.toBeNull()
  })

  it('renders the neutral glyph — and no blur — when there is no photo at all', () => {
    const { container } = render(<Avatar src={null} blurhash={BLURHASH} />)
    expect(photo(container)).toBeNull()
    expect(blur(container)).toBeNull()
    expect(container.querySelector('.avatar')?.textContent).toContain('◍')
  })

  it('falls back to the original photo when the compressed one fails (#252/#254)', () => {
    const { container } = render(
      <Avatar src="http://compressed/a.jpg" originalSrc="http://original/a.jpg" />,
    )
    expect(photo(container)!.getAttribute('src')).toBe('http://compressed/a.jpg')

    fireEvent.error(photo(container)!)
    expect(photo(container)!.getAttribute('src')).toBe('http://original/a.jpg')

    // A failing original drops to the placeholder rather than looping.
    fireEvent.error(photo(container)!)
    expect(photo(container)).toBeNull()
    expect(container.querySelector('.avatar')?.textContent).toContain('◍')
  })
})
