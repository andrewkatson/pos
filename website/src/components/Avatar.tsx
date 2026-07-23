import { useState } from 'react'

/**
 * A user's profile photo (issue #7), rendered as a circular avatar next to
 * their name everywhere it appears. Falls back the same way post images do:
 * the compressed URL first, then the full-resolution original if that fails to
 * load (the compressed copy is produced by an async Lambda and can 404 briefly
 * — see issues #252/#254), and finally the neutral `◍` placeholder glyph when
 * there is no photo at all or both URLs fail.
 *
 * The compressed→original switch uses a flag that flips at most once rather than
 * mutating `img.src`, so a failing original leaves the placeholder instead of a
 * reload loop (mirroring PostThumbnail).
 */
function Avatar({
  src,
  originalSrc,
  username,
  size = 'sm',
  className,
}: {
  /** Compressed avatar URL, or null/undefined when the user has no photo. */
  src?: string | null
  /** Full-resolution fallback used if the compressed URL fails to load. */
  originalSrc?: string | null
  /** The user the photo belongs to, for the alt text. */
  username: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}) {
  const [useOriginal, setUseOriginal] = useState(false)
  const [failed, setFailed] = useState(false)

  const resolved = useOriginal && originalSrc ? originalSrc : src
  const classes = ['avatar', `avatar--${size}`, className].filter(Boolean).join(' ')

  if (!resolved || failed) {
    return (
      <span className={classes} aria-hidden="true">
        ◍
      </span>
    )
  }

  return (
    <img
      className={classes}
      src={resolved}
      alt={`${username}'s profile photo`}
      onError={() => {
        if (!useOriginal && originalSrc) {
          setUseOriginal(true)
        } else {
          setFailed(true)
        }
      }}
    />
  )
}

export default Avatar
