import type { FeedPost } from '../api/types'

/**
 * A post's grid/feed thumbnail image. Renders the compressed `image_url` and, if
 * that fails to load, falls back to the full-resolution `original_image_url`.
 *
 * The compressed copy is produced by an async Lambda, so a just-posted (or
 * recently hidden-pending-appeal) image can 404 in the compressed bucket for a
 * while; without the fallback those tiles render as broken images until the user
 * re-logs in. See issues #252 and #254.
 */
function PostThumbnail({ post }: { post: Pick<FeedPost, 'image_url' | 'original_image_url' | 'caption'> }) {
  return (
    <img
      src={post.image_url}
      alt={post.caption}
      onError={e => {
        const img = e.currentTarget
        if (post.original_image_url && img.src !== post.original_image_url) {
          img.src = post.original_image_url
        }
      }}
    />
  )
}

export default PostThumbnail
