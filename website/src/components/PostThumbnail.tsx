import { useState } from 'react'
import type { FeedPost } from '../api/types'

/**
 * A post's grid/feed thumbnail image. Renders the compressed `image_url` and, if
 * that fails to load, falls back to the full-resolution `original_image_url`.
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
 */
function PostThumbnail({ post }: { post: Pick<FeedPost, 'image_url' | 'original_image_url' | 'caption'> }) {
  const [useOriginal, setUseOriginal] = useState(false)
  const src = useOriginal && post.original_image_url ? post.original_image_url : post.image_url
  return (
    <img
      src={src}
      alt={post.caption}
      onError={() => {
        if (!useOriginal && post.original_image_url) {
          setUseOriginal(true)
        }
      }}
    />
  )
}

export default PostThumbnail
