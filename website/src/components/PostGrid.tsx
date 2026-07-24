import { useNavigate } from 'react-router-dom'
import type { FeedPost } from '../api/types'
import PostThumbnail from './PostThumbnail'
import PostActionBar from './PostActionBar'
import { usePostActions } from './usePostActions'

interface PostGridProps {
  posts: FeedPost[]
  /** The signed-in user, so own posts get Delete instead of Report. */
  currentUsername: string | null
  /** Called after a post is deleted so the owner can drop it from its list. */
  onPostDeleted: (postIdentifier: string) => void
  /** Called after a post is unsaved. The Saved Posts screen passes this to drop
   * the tile; other grids leave it in place (issue #193). */
  onPostUnsaved?: (postIdentifier: string) => void
  /** Surfaces a failed action to the parent's error banner. */
  onError: (message: string) => void
}

/** Overlay label for the author's own pending/rejected grid tiles (#282). */
function statusBadgeLabel(post: FeedPost): string | null {
  if (post.status === 'pending') return 'In review'
  if (post.status === 'rejected') return 'Hidden — you can appeal'
  return null
}

/**
 * The profile post grid: thumbnails that open the post, each with in-place like,
 * report, retract-report and delete controls (issue #267). Used for your own
 * profile (the Profile tab) and anyone else's, so both behave identically.
 *
 * Classification state (#282) only ever arrives on your own posts — everyone
 * else's pending/hidden posts are filtered out server-side — so the badge
 * simply appears when the server sends a status.
 */
function PostGrid({ posts, currentUsername, onPostDeleted, onPostUnsaved, onError }: PostGridProps) {
  const navigate = useNavigate()
  const { stateFor, toggleLike, toggleSave, openMenu, dialogs } = usePostActions({
    currentUsername,
    onPostDeleted,
    onPostUnsaved,
    onError,
  })

  return (
    <>
      <div className="post-grid">
        {posts.map(post => {
          const badge = statusBadgeLabel(post)
          return (
            <div key={post.post_identifier} className="post-grid__item">
              <button
                type="button"
                className="post-grid__cell"
                // The explicit aria-label overrides the accessible-name
                // calculation, so the review state must be part of it for
                // assistive tech to announce it (the visual badge below is
                // otherwise invisible to screen readers).
                aria-label={
                  badge
                    ? `Post by ${post.author_username} — ${badge}`
                    : `Post by ${post.author_username}`
                }
                onClick={() => navigate(`/post/${post.post_identifier}`)}
              >
                <PostThumbnail post={post} />
                {badge && <span className="post-grid__status-badge">{badge}</span>}
              </button>
              <PostActionBar
                post={post}
                state={stateFor(post)}
                onToggleLike={toggleLike}
                onToggleSave={toggleSave}
                onOpenMenu={openMenu}
              />
            </div>
          )
        })}
      </div>
      {dialogs}
    </>
  )
}

export default PostGrid
