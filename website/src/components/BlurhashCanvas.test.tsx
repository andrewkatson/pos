import { render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import BlurhashCanvas from './BlurhashCanvas'

// A valid canonical BlurHash (the Wolt example string), and one that isn't.
const BLURHASH = 'LEHV6nWB2yk8pyo0adR*.7kCMdnj'
const OTHER_BLURHASH = 'L6PZfSi_.AyE_3t7t7R**0o#DgR4'
const MALFORMED = 'not-a-blurhash'

/**
 * jsdom implements no 2d context, so `getContext('2d')` returns null and the
 * component's draw is skipped entirely. Stand a minimal one in and record what
 * it is asked to do, which is the only way to assert on pixels here.
 */
function stubContext() {
  const ctx = {
    createImageData: (width: number, height: number) => ({
      data: new Uint8ClampedArray(width * height * 4),
    }),
    putImageData: vi.fn(),
    clearRect: vi.fn(),
  }
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    ctx as unknown as CanvasRenderingContext2D,
  )
  return ctx
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('BlurhashCanvas', () => {
  it('draws the decoded preview for a valid hash', () => {
    const ctx = stubContext()

    render(<BlurhashCanvas hash={BLURHASH} className="avatar__blur" />)

    expect(ctx.putImageData).toHaveBeenCalledTimes(1)
    expect(ctx.clearRect).not.toHaveBeenCalled()
  })

  it('redraws when the hash changes to another valid one', () => {
    const ctx = stubContext()
    const { rerender } = render(<BlurhashCanvas hash={BLURHASH} className="avatar__blur" />)

    rerender(<BlurhashCanvas hash={OTHER_BLURHASH} className="avatar__blur" />)

    expect(ctx.putImageData).toHaveBeenCalledTimes(2)
    expect(ctx.clearRect).not.toHaveBeenCalled()
  })

  it('clears the canvas when a valid hash is replaced by a malformed one', () => {
    // The canvas is reused across hash changes, so bailing out of the decode
    // without clearing would leave the first hash's pixels standing in as the
    // second image's placeholder — a blurred preview of the wrong photo.
    const ctx = stubContext()
    const { rerender } = render(<BlurhashCanvas hash={BLURHASH} className="avatar__blur" />)
    expect(ctx.putImageData).toHaveBeenCalledTimes(1)

    rerender(<BlurhashCanvas hash={MALFORMED} className="avatar__blur" />)

    expect(ctx.clearRect).toHaveBeenCalledTimes(1)
    // And nothing new was drawn over it.
    expect(ctx.putImageData).toHaveBeenCalledTimes(1)
  })

  it('renders without throwing when the hash is malformed from the start', () => {
    const ctx = stubContext()

    const { container } = render(<BlurhashCanvas hash={MALFORMED} className="avatar__blur" />)

    expect(container.querySelector('canvas.avatar__blur')).not.toBeNull()
    expect(ctx.putImageData).not.toHaveBeenCalled()
  })
})
