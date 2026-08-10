import { useEffect, useRef } from 'react'
import { decode } from 'blurhash'

// The BlurHash is decoded at a small size and CSS-scaled up to fill its box; a
// handful of pixels is all a blurred preview needs and keeps the decode cheap.
const BLUR_DECODE_SIZE = 32

/**
 * A blurred preview decoded from a BlurHash, drawn to a small canvas and
 * CSS-scaled to fill its box. Shown underneath a real <img> while that image
 * loads (and left in place if it never loads) so the slot is a soft blur of the
 * actual photo instead of a flat grey square.
 *
 * Shared by post images (issue #387, via PostThumbnail) and profile photos
 * (issue #460, via Avatar); the caller supplies the class that positions it,
 * since the two sit in differently-shaped boxes.
 */
function BlurhashCanvas({ hash, className }: { hash: string; className: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    // A malformed hash makes decode throw; swallow it so a bad value just
    // yields no placeholder rather than crashing the render.
    let pixels: Uint8ClampedArray
    try {
      pixels = decode(hash, BLUR_DECODE_SIZE, BLUR_DECODE_SIZE)
    } catch {
      return
    }
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const imageData = ctx.createImageData(BLUR_DECODE_SIZE, BLUR_DECODE_SIZE)
    imageData.data.set(pixels)
    ctx.putImageData(imageData, 0, 0)
  }, [hash])
  return (
    <canvas
      ref={canvasRef}
      className={className}
      width={BLUR_DECODE_SIZE}
      height={BLUR_DECODE_SIZE}
      aria-hidden="true"
    />
  )
}

export default BlurhashCanvas
