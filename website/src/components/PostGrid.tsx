import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
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
  /** Tiles only, no action bar: for a signed-out visitor on a shared profile
   * (issue #510), who can open a post but has no session to like, save, report
   * or delete with. Sharing a single post is offered on the post page itself. */
  readOnly?: boolean
  /** Asks the owner for the next batch while the grid doesn't yet fill the
   * screen or ends on a partial row (issue #538). The owner passes it only
   * while another batch may exist and none is in flight, and omits it
   * otherwise; each new batch re-checks, so loading stops once the grid is
   * filled. "Load more" still pages past that. */
  onFillRequest?: () => void
}

/** Columns in `.post-grid` (MainApp.css); keep the two in sync. */
const POST_GRID_COLUMNS = 3

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
function PostGrid({
  posts,
  currentUsername,
  onPostDeleted,
  onPostUnsaved,
  onError,
  readOnly = false,
  onFillRequest,
}: PostGridProps) {
  const navigate = useNavigate()
  const gridRef = useRef<HTMLDivElement>(null)
  const { stateFor, toggleLike, toggleSave, openMenu, openMenuPostId, openLikes, dialogs } =
    usePostActions({
      currentUsername,
      onPostDeleted,
      onPostUnsaved,
      onError,
    })

  // One batch of 10 leaves a partial last row and, at common window sizes,
  // empty screen below the grid until "Load more" is pressed (issue #538), so
  // keep asking for batches until the grid ends on a full row and runs past
  // the bottom of the viewport. Re-checked on resize, since zooming out or
  // enlarging the window can open up space again.
  useEffect(() => {
    if (!onFillRequest || posts.length === 0) return
    let requested = false
    const check = () => {
      const grid = gridRef.current
      if (requested || !grid) return
      const rect = grid.getBoundingClientRect()
      // A grid with no layout box isn't on screen, so there's nothing to fill.
      if (rect.height === 0) return
      const endsOnPartialRow = posts.length % POST_GRID_COLUMNS !== 0
      const leavesGapBelow = rect.bottom < window.innerHeight
      if (endsOnPartialRow || leavesGapBelow) {
        // At most one request per check cycle: the owner withdraws the
        // callback while that batch loads, which re-runs this effect.
        requested = true
        onFillRequest()
      }
    }
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [posts.length, onFillRequest])

  return (
    <>
      <div ref={gridRef} className="post-grid">
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
              {!readOnly && (
                <PostActionBar
                  post={post}
                  state={stateFor(post)}
                  onToggleLike={toggleLike}
                  onToggleSave={toggleSave}
                  onOpenMenu={openMenu}
                  isMenuOpen={openMenuPostId === post.post_identifier}
                  onOpenLikes={openLikes}
                />
              )}
            </div>
          )
        })}
      </div>
      {!readOnly && dialogs}
    </>
  )
}

export default PostGrid
