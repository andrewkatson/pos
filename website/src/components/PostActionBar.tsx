import type { FeedPost } from '../api/types'
import { formatRelativeTime } from '../utils/relativeTime'
import type { PostActionState } from './usePostActions'

interface PostActionBarProps {
  post: FeedPost
  state: PostActionState
  onToggleLike: (post: FeedPost) => void
  onToggleSave: (post: FeedPost) => void
  onOpenMenu: (post: FeedPost) => void
  /** Opens the post; used by the comment-count indicator (issue #249). */
  onOpenPost?: (post: FeedPost) => void
  /** Shows the comment count and the post time. Feed rows have room for these
   * (issue #249); the square profile tiles don't. */
  showDetails?: boolean
}

/**
 * The like / reported-flag / options row rendered beneath a post in a list, so
 * posts can be acted on without opening them (issue #267). Pair it with
 * usePostActions, which owns the state and the confirmation dialogs.
 *
 * On the feed it also carries a tappable comment count and how long ago the
 * post was made (issue #249).
 */
function PostActionBar({
  post,
  state,
  onToggleLike,
  onToggleSave,
  onOpenMenu,
  onOpenPost,
  showDetails = false,
}: PostActionBarProps) {
  // '' when creation_time is missing or unparseable, so one value drives both
  // the guard and the rendered label.
  const postTime = post.creation_time ? formatRelativeTime(post.creation_time) : ''
  // Left undefined rather than coerced to 0: a payload that predates the field
  // has no count to show, and "0 comments" would be a claim rather than an
  // omission. Same treatment as the timestamp above.
  const commentCount = post.comment_count

  return (
    <div className="post-actions">
      {/* The backend rejects liking your own post, so the control is hidden for
          it — matching the post detail view. */}
      {!state.isOwn && (
        <button
          type="button"
          className="heart"
          aria-label={state.isLiked ? 'Unlike post' : 'Like post'}
          aria-pressed={state.isLiked}
          onClick={() => onToggleLike(post)}
        >
          {state.isLiked ? '♥' : '♡'}
        </button>
      )}
      <span className="post-actions__count">{state.likeCount}</span>

      {/* Tapping the comment count opens the post, where the threads live. */}
      {showDetails && onOpenPost && commentCount !== undefined && (
        <button
          type="button"
          className="post-actions__comments"
          aria-label={`${commentCount} ${commentCount === 1 ? 'comment' : 'comments'}, open post`}
          onClick={() => onOpenPost(post)}
        >
          <span aria-hidden="true">💬</span>
          <span className="post-actions__count">{commentCount}</span>
        </button>
      )}

      {/* Rendered bare, like the post detail and comment timestamps do — the
          helper already returns the whole label. */}
      {showDetails && postTime && <span className="post-actions__time">{postTime}</span>}

      {state.isReported && (
        <span className="flag-icon" aria-label="You reported this post">
          ⚑
        </span>
      )}
      {/* Saving is a personal bookmark, so unlike the heart it's offered on
          every post, including your own (issue #193). */}
      <button
        type="button"
        className="bookmark"
        aria-label={state.isSaved ? 'Unsave post' : 'Save post'}
        aria-pressed={state.isSaved}
        onClick={() => onToggleSave(post)}
      >
        {state.isSaved ? '🔖' : '🏷️'}
      </button>
      <button
        type="button"
        className="post-actions__menu"
        aria-label={`Options for post by ${post.author_username}`}
        aria-haspopup="dialog"
        onClick={() => onOpenMenu(post)}
      >
        ⋯
      </button>
    </div>
  )
}

export default PostActionBar
