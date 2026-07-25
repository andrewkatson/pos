import { useState } from 'react'

interface AvatarProps {
  /** Compressed avatar URL, or null/undefined when the user has no photo. */
  src?: string | null
  /** Full-resolution fallback used if the compressed URL fails to load. */
  originalSrc?: string | null
  /** Whose avatar this is. Optional and currently unused: the avatar is
   * decorative (the username is always rendered adjacent, so the image carries
   * an empty alt); kept for callers and any future non-decorative use. */
  username?: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

/**
 * A user's profile photo (issue #7), rendered as a circular avatar next to
 * their name everywhere it appears. Falls back the same way post images do:
 * the compressed URL first, then the full-resolution original if that fails to
 * load (the compressed copy is produced by an async Lambda and can 404 briefly
 * — see issues #252/#254), and finally the neutral `◍` placeholder glyph when
 * there is no photo at all or both URLs fail.
 *
 * The inner view is keyed on the backing URLs, so changing them (a new upload, a
 * refreshed signed URL, or the compressed copy becoming available) remounts it
 * with fresh fallback state — React's "reset state with a key" pattern, which
 * avoids both a render-phase setState and a state-updating effect.
 */
function Avatar(props: AvatarProps) {
  return <AvatarImage key={`${props.src ?? ''}|${props.originalSrc ?? ''}`} {...props} />
}

function AvatarImage({ src, originalSrc, size = 'sm', className }: AvatarProps) {
  // The compressed→original switch flips at most once, so a failing original
  // leaves the placeholder instead of a reload loop (mirroring PostThumbnail).
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
      // Decorative: the username is always rendered right next to the avatar, so
      // an alt would make screen readers announce it twice. Empty alt (like the
      // aria-hidden placeholder) keeps assistive tech from reading the avatar.
      alt=""
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
