import { useState, type MouseEventHandler } from 'react'
import type { FeedPost } from '../api/types'
import BlurhashCanvas from './BlurhashCanvas'
import CaptionTile from './CaptionTile'

/**
 * A post's image with the compressed→original fallback: renders the compressed
 * `image_url` and, if that fails to load, falls back to the full-resolution
 * `original_image_url`. Used for grid/feed thumbnails and, via the passthrough
 * `className`/`onDoubleClick` props, the post detail page's full-size image.
 *
 * The compressed copy is produced by an async Lambda, so a just-posted (or
 * recently hidden-pending-appeal) image can 404 in the compressed bucket for a
 * while; without the fallback those tiles render as broken images until the user
 * re-logs in. See issues #252 and #254.
 *
 * The compressed→original switch is driven by a `useOriginal` flag (mirroring the
 * iOS/Android grids) rather than by mutating `img.src` and comparing it back: the
 * `HTMLImageElement.src` property is a normalized/resolved URL that may not
 * string-equal the assigned value, so a comparison guard could fail to stop a
 * repeated-load loop if the original also 404s. The flag flips at most once, so a
 * failing original just leaves a broken image — never a reload loop. Each grid
 * keys this component by post id, so a new post gets fresh state.
 *
 * While the image loads, a BlurHash preview (issue #387) sits behind it and is
 * revealed instead of a grey square; it is removed once the image paints and
 * stays put if the image never loads at all.
 */
function PostThumbnail({
  post,
  className,
  variant,
  onDoubleClick,
}: {
  post: Pick<
    FeedPost,
    | 'image_url'
    | 'original_image_url'
    | 'image_blurhash'
    | 'caption'
    | 'caption_font'
    | 'background_color'
  >
  className?: string
  variant?: 'detail' | 'thumb'
  onDoubleClick?: MouseEventHandler<HTMLElement>
}) {
  const [useOriginal, setUseOriginal] = useState(false)
  const [loaded, setLoaded] = useState(false)
  if (post.image_url === null) {
    // A text-only post (#307) has no image; render its caption as the tile,
    // styled with the author's chosen font/background color (issue #318).
    return (
      <CaptionTile
        caption={post.caption}
        captionFont={post.caption_font}
        backgroundColor={post.background_color}
        variant={variant}
        className={className}
        onDoubleClick={onDoubleClick ? (e) => onDoubleClick(e) : undefined}
      />
    )
  }
  const src = useOriginal && post.original_image_url ? post.original_image_url : post.image_url
  const blurhash = post.image_blurhash
  // The passed `className` (e.g. `detail-image`) goes on the wrapper, which
  // clips its contents (`.post-thumbnail { overflow: hidden }`): that way the
  // caller's sizing/rounding/background applies to the whole tile and the
  // BlurHash canvas shows through instead of being hidden behind the image's own
  // background. The image itself is transparent so it never paints over the blur.
  return (
    <span className={className ? `post-thumbnail ${className}` : 'post-thumbnail'}>
      {blurhash && !loaded && (
        <BlurhashCanvas hash={blurhash} className="post-thumbnail__blur" />
      )}
      <img
        className="post-thumbnail__img"
        src={src}
        alt={post.caption}
        onDoubleClick={onDoubleClick}
        onLoad={() => setLoaded(true)}
        onError={() => {
          if (!useOriginal && post.original_image_url) {
            setUseOriginal(true)
          }
        }}
      />
    </span>
  )
}

export default PostThumbnail
