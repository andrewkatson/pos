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
  /** Surfaces a failed action to the parent's error banner. */
  onError: (message: string) => void
}

/**
 * The profile post grid: thumbnails that open the post, each with in-place like,
 * report, retract-report and delete controls (issue #267). Used for your own
 * profile (the Profile tab) and anyone else's, so both behave identically.
 */
function PostGrid({ posts, currentUsername, onPostDeleted, onError }: PostGridProps) {
  const navigate = useNavigate()
  const { stateFor, toggleLike, openMenu, dialogs } = usePostActions({
    currentUsername,
    onPostDeleted,
    onError,
  })

  return (
    <>
      <div className="post-grid">
        {posts.map(post => (
          <div key={post.post_identifier} className="post-grid__item">
            <button
              type="button"
              className="post-grid__cell"
              aria-label={`Post by ${post.author_username}`}
              onClick={() => navigate(`/post/${post.post_identifier}`)}
            >
              <PostThumbnail post={post} />
            </button>
            <PostActionBar
              post={post}
              state={stateFor(post)}
              onToggleLike={toggleLike}
              onOpenMenu={openMenu}
            />
          </div>
        ))}
      </div>
      {dialogs}
    </>
  )
}

export default PostGrid
