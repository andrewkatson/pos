import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { apiClient } from '../api/client'
import { getCurrentUsername } from '../api/session'
import type { Comment, PostDetails } from '../api/types'
import { isWithinLimit, MAX_COMMENT_LENGTH } from '../auth/requirements'
import CaptionTile from '../components/CaptionTile'
import CharacterCounter from '../components/CharacterCounter'
import { formatRelativeTime } from '../utils/relativeTime'
import './MainApp.css'

/** A comment enriched with the local like/report state the API doesn't return. */
interface CommentView {
  id: string
  threadId: string
  authorUsername: string
  body: string
  createdTime: string
  likeCount: number
  isLiked: boolean
  isReported: boolean
  // The backend rejects liking your own comment, so the UI hides the like
  // control for comments the current user authored.
  isOwn: boolean
}

interface ThreadView {
  threadId: string
  comments: CommentView[]
}

type ReportTarget = { type: 'post' } | { type: 'comment'; comment: CommentView }
type DeleteTarget = { type: 'post' } | { type: 'comment'; comment: CommentView }
// The comment composer is shared between a brand-new post comment and a reply
// to an existing thread, so both go through the same character-limit dialog.
type ComposerTarget = { type: 'post' } | { type: 'reply'; thread: ThreadView }

/**
 * Full post view: image, like count, caption, and threaded comments with
 * replies. Supports liking/reporting the post and each comment, and adding new
 * comments or replies. Mirrors iOS PostDetailView / PostDetailViewModel.
 *
 * The web API doesn't report whether the current user has liked a post/comment,
 * so like state is tracked locally and applied optimistically.
 *
 * The inner view is keyed by postId so navigating to a different post fully
 * resets its state instead of briefly showing the previous post's data.
 */
function PostDetailPage() {
  const { postId = '' } = useParams<{ postId: string }>()
  // Comments/likes/reports require a session, so require one like HomePage.
  if (!apiClient.isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return <PostDetailView key={postId} postId={postId} />
}

function PostDetailView({ postId }: { postId: string }) {
  const navigate = useNavigate()

  // The signed-in user, read once. Used to hide the like control on the user's
  // own post/comments since the backend rejects liking your own content.
  const [currentUsername] = useState(() => getCurrentUsername())

  // Track mount state so async loads that resolve after navigating away don't
  // set state on an unmounted view.
  const isMounted = useRef(true)
  useEffect(() => {
    isMounted.current = true
    return () => {
      isMounted.current = false
    }
  }, [])

  const [post, setPost] = useState<PostDetails | null>(null)
  const [postLikeCount, setPostLikeCount] = useState(0)
  const [postLiked, setPostLiked] = useState(false)
  const [postReported, setPostReported] = useState(false)
  const [threads, setThreads] = useState<ThreadView[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [notFound, setNotFound] = useState(false)

  // A single composer dialog drives both new post comments and thread replies,
  // so both surfaces show the same character-limit popup instead of an inline
  // field duplicated in every thread (issues #266, #289, #290).
  const [composer, setComposer] = useState<ComposerTarget | null>(null)
  const [composerText, setComposerText] = useState('')
  const [reportTarget, setReportTarget] = useState<ReportTarget | null>(null)
  const [reportReason, setReportReason] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  // Ids of comments whose thread below them is collapsed. Tapping a comment's
  // username/time header toggles it (issue #243).
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set())

  function toggleCollapsed(id: string) {
    setCollapsedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // Local like/report state, kept in refs so the in-app reload after posting a
  // comment/reply doesn't drop it (the API only returns server-side counts,
  // never per-user like flags). This is in-memory only and resets on a full
  // page reload.
  const likedCommentIds = useRef<Set<string>>(new Set())
  const reportedCommentIds = useRef<Set<string>>(new Set())

  // Single in-flight guard shared by every loadAll() caller (initial load,
  // pull-to-refresh, and the post-comment/reply reloads) so two loads can't
  // overlap and clobber each other's state or duplicate API requests. A request
  // that arrives mid-load isn't dropped — it sets pendingReloadRef so the load
  // re-runs once afterward, ensuring the freshest state (e.g. a just-posted
  // comment) is always reflected.
  const isLoadingRef = useRef(false)
  const pendingReloadRef = useRef(false)

  const loadAll = useCallback(async () => {
    // A load is already running: request a follow-up run instead of dropping
    // this call, then let the in-flight load pick it up when it finishes.
    if (isLoadingRef.current) {
      pendingReloadRef.current = true
      return
    }
    isLoadingRef.current = true

    const performLoad = async () => {
      const toView = (c: Comment, threadId: string): CommentView => ({
        id: c.comment_identifier,
        threadId,
        authorUsername: c.author_username,
        body: c.body,
        createdTime: c.creation_time,
        likeCount: c.comment_likes,
        isLiked: likedCommentIds.current.has(c.comment_identifier),
        isReported: reportedCommentIds.current.has(c.comment_identifier),
        isOwn: c.author_username === currentUsername,
      })

      // A failure to load the post itself is the only "not found" case. Comment
      // loading is handled separately so a transient comments error doesn't hide
      // a post that loaded fine.
      let details: PostDetails
      try {
        details = await apiClient.getPostDetails(postId)
      } catch {
        if (isMounted.current) {
          setNotFound(true)
          setIsLoading(false)
        }
        return
      }
      if (!isMounted.current) return
      setPost(details)
      setPostLikeCount(details.post_likes)

      try {
        const refs = await apiClient.getCommentsForPost(postId, 0)
        const threadLists = await Promise.all(
          refs.map(async ref => {
            const comments = await apiClient.getCommentsForThread(
              ref.comment_thread_identifier,
              0,
            )
            return { threadId: ref.comment_thread_identifier, comments }
          }),
        )
        if (!isMounted.current) return

        const built: ThreadView[] = threadLists
          .filter(t => t.comments.length > 0)
          .map(t => ({
            threadId: t.threadId,
            comments: t.comments
              .slice()
              .sort((a, b) => a.creation_time.localeCompare(b.creation_time))
              .map(c => toView(c, t.threadId)),
          }))
          .sort((a, b) =>
            (a.comments[0]?.createdTime ?? '').localeCompare(b.comments[0]?.createdTime ?? ''),
          )
        setThreads(built)
        // Clear any stale "failed to load comments" message from a prior attempt.
        setErrorMessage(null)
      } catch {
        if (isMounted.current) setErrorMessage('Failed to load comments.')
      } finally {
        if (isMounted.current) setIsLoading(false)
      }
    }

    try {
      // Re-run while another load was requested mid-flight (and we're still
      // mounted), so a coalesced refresh/post-comment reload isn't lost.
      do {
        pendingReloadRef.current = false
        await performLoad()
      } while (pendingReloadRef.current && isMounted.current)
    } finally {
      isLoadingRef.current = false
    }
  }, [postId, currentUsername])

  // Kick the initial load off a microtask so the fetch's setState calls don't
  // run synchronously inside the effect (React flags that as cascading renders).
  useEffect(() => {
    void Promise.resolve().then(loadAll)
  }, [loadAll])

  // Manual refresh — the web equivalent of the iOS/Android pull-to-refresh — so
  // comments added by others can be pulled in without a full page reload.
  async function refreshComments() {
    if (isRefreshing) return
    setIsRefreshing(true)
    try {
      await loadAll()
    } finally {
      if (isMounted.current) setIsRefreshing(false)
    }
  }

  // ---- Post actions ----

  // The backend rejects liking your own post, so don't optimistically like it.
  const isOwnPost = post?.author_username === currentUsername

  async function togglePostLike() {
    if (isOwnPost) return
    const liking = !postLiked
    setPostLiked(liking)
    setPostLikeCount(n => (liking ? n + 1 : Math.max(0, n - 1)))
    try {
      if (liking) await apiClient.likePost(postId)
      else await apiClient.unlikePost(postId)
    } catch (err) {
      // Revert on failure.
      setPostLiked(!liking)
      setPostLikeCount(n => (liking ? Math.max(0, n - 1) : n + 1))
      setErrorMessage((err as Error).message ?? 'Action failed.')
    }
  }

  // ---- Comment actions ----

  function mutateComment(id: string, fn: (c: CommentView) => CommentView) {
    setThreads(prev =>
      prev.map(thread => ({
        ...thread,
        comments: thread.comments.map(c => (c.id === id ? fn(c) : c)),
      })),
    )
  }

  async function toggleCommentLike(comment: CommentView) {
    if (comment.isOwn) return
    const liking = !comment.isLiked
    if (liking) likedCommentIds.current.add(comment.id)
    else likedCommentIds.current.delete(comment.id)
    mutateComment(comment.id, c => ({
      ...c,
      isLiked: liking,
      likeCount: liking ? c.likeCount + 1 : Math.max(0, c.likeCount - 1),
    }))
    try {
      if (liking)
        await apiClient.likeComment(postId, comment.threadId, comment.id)
      else await apiClient.unlikeComment(postId, comment.threadId, comment.id)
    } catch (err) {
      if (liking) likedCommentIds.current.delete(comment.id)
      else likedCommentIds.current.add(comment.id)
      mutateComment(comment.id, c => ({
        ...c,
        isLiked: !liking,
        likeCount: liking ? Math.max(0, c.likeCount - 1) : c.likeCount + 1,
      }))
      setErrorMessage((err as Error).message ?? 'Action failed.')
    }
  }

  function openComposer(target: ComposerTarget) {
    setComposerText('')
    setComposer(target)
  }

  // Submitting closes the dialog immediately and clears the text before the
  // request is sent, so repeated taps can't post the same comment twice and the
  // keyboard/dialog disappear at once (issue #291).
  async function submitComposer() {
    const text = composerText.trim()
    const target = composer
    if (!text || !target) return
    setComposer(null)
    setComposerText('')
    try {
      if (target.type === 'reply') {
        await apiClient.replyToCommentThread(postId, target.thread.threadId, text)
      } else {
        await apiClient.commentOnPost(postId, text)
      }
      await loadAll()
    } catch (err) {
      const verb = target.type === 'reply' ? 'reply' : 'comment'
      setErrorMessage((err as Error).message ?? `Failed to post ${verb}.`)
    }
  }

  // ---- Reporting ----

  async function submitReport() {
    const reason = reportReason.trim()
    const target = reportTarget
    if (!reason || !target) return
    try {
      if (target.type === 'post') {
        await apiClient.reportPost(postId, reason)
        setPostReported(true)
      } else {
        await apiClient.reportComment(
          postId,
          target.comment.threadId,
          target.comment.id,
          reason,
        )
        reportedCommentIds.current.add(target.comment.id)
        mutateComment(target.comment.id, c => ({ ...c, isReported: true }))
      }
    } catch (err) {
      setErrorMessage((err as Error).message ?? 'Failed to report.')
    } finally {
      setReportReason('')
      setReportTarget(null)
    }
  }

  // ---- Deleting (own content only) ----

  async function submitDelete() {
    const target = deleteTarget
    if (!target) return
    try {
      if (target.type === 'post') {
        await apiClient.deletePost(postId)
        // The post no longer exists; leave the detail view for the feed.
        // (the finally block clears deleteTarget)
        navigate('/home')
        return
      }
      await apiClient.deleteComment(postId, target.comment.threadId, target.comment.id)
      // Reload so the deleted comment disappears from its thread.
      await loadAll()
    } catch (err) {
      setErrorMessage((err as Error).message ?? 'Failed to delete.')
    } finally {
      setDeleteTarget(null)
    }
  }

  if (isLoading && !post) {
    return (
      <div className="app-shell">
        <DetailBar onBack={() => navigate(-1)} />
        <div className="center-spinner">
          <span className="spinner" />
        </div>
      </div>
    )
  }

  if (notFound || !post) {
    return (
      <div className="app-shell">
        <DetailBar onBack={() => navigate(-1)} />
        <main className="app-content">
          <p className="muted">Post not found.</p>
        </main>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <DetailBar onBack={() => navigate(-1)} />

      <main className="app-content">
        {errorMessage && (
          <div className="auth-error" role="alert">
            <p>{errorMessage}</p>
            <button
              type="button"
              className="auth-error__dismiss"
              aria-label="Dismiss error"
              onClick={() => setErrorMessage(null)}
            >
              ✕
            </button>
          </div>
        )}

        {post.image_url === null ? (
          // A text-only post (#307): the caption is the tile, double-tap still likes.
          <CaptionTile
            caption={post.caption}
            variant="detail"
            onDoubleClick={isOwnPost ? undefined : togglePostLike}
          />
        ) : (
          <img
            className="detail-image"
            src={post.image_url}
            alt={post.caption}
            onDoubleClick={isOwnPost ? undefined : togglePostLike}
          />
        )}

        <div className="detail-meta">
          {!isOwnPost && (
            <button
              type="button"
              className="heart"
              aria-label={postLiked ? 'Unlike post' : 'Like post'}
              aria-pressed={postLiked}
              onClick={togglePostLike}
            >
              {postLiked ? '♥' : '♡'}
            </button>
          )}
          <span className="detail-likes">{postLikeCount} likes</span>
          {postReported && (
            <span className="flag-icon" aria-label="Reported">
              ⚑
            </span>
          )}
          {/* You can't report your own post — own posts offer Delete instead. */}
          {isOwnPost ? (
            <button
              type="button"
              className="app-bar__back"
              style={{ marginLeft: 'auto' }}
              onClick={() => setDeleteTarget({ type: 'post' })}
            >
              Delete
            </button>
          ) : (
            <button
              type="button"
              className="app-bar__back"
              style={{ marginLeft: 'auto' }}
              onClick={() => {
                setReportReason('')
                setReportTarget({ type: 'post' })
              }}
            >
              Report
            </button>
          )}
        </div>

        <p className="detail-caption">
          <button
            type="button"
            className="feed-post__author"
            style={{ display: 'inline', padding: 0 }}
            onClick={() => navigate(`/profile/${encodeURIComponent(post.author_username)}`)}
          >
            {post.author_username}
          </button>{' '}
          {post.caption}
        </p>

        <div className="comment-form">
          <button
            type="button"
            className="comment-compose-trigger"
            onClick={() => openComposer({ type: 'post' })}
          >
            Add a comment...
          </button>
        </div>

        <h2 className="app-bar__title" style={{ fontSize: '1rem' }}>
          Comments
        </h2>

        <button
          type="button"
          className="refresh-button"
          aria-label="Refresh comments"
          disabled={isRefreshing}
          onClick={refreshComments}
        >
          <span aria-hidden="true">↻</span> Refresh
        </button>

        {threads.length === 0 ? (
          <p className="muted">No comments yet. Be the first!</p>
        ) : (
          threads.map(thread => {
            // Hide every comment that sits below the first collapsed one in the
            // thread, so tapping a comment's header folds away the replies under
            // it (issue #243).
            const collapseAt = thread.comments.findIndex(c => collapsedIds.has(c.id))
            const visible =
              collapseAt === -1 ? thread.comments : thread.comments.slice(0, collapseAt + 1)
            const [root, ...replies] = visible
            return (
              <div key={thread.threadId} className="comment-thread">
                {root && (
                  <CommentRow
                    comment={root}
                    isCollapsed={collapsedIds.has(root.id)}
                    onToggleCollapse={() => toggleCollapsed(root.id)}
                    onToggleLike={() => toggleCommentLike(root)}
                    onReport={() => {
                      setReportReason('')
                      setReportTarget({ type: 'comment', comment: root })
                    }}
                    onDelete={() => setDeleteTarget({ type: 'comment', comment: root })}
                    onNavigate={() =>
                      navigate(`/profile/${encodeURIComponent(root.authorUsername)}`)
                    }
                  />
                )}
                <button
                  type="button"
                  className="comment-reply-btn"
                  onClick={() => openComposer({ type: 'reply', thread })}
                >
                  Reply
                </button>
                {replies.length > 0 && (
                  <div className="comment-replies">
                    {replies.map(reply => (
                      <CommentRow
                        key={reply.id}
                        comment={reply}
                        isCollapsed={collapsedIds.has(reply.id)}
                        onToggleCollapse={() => toggleCollapsed(reply.id)}
                        onToggleLike={() => toggleCommentLike(reply)}
                        onReport={() => {
                          setReportReason('')
                          setReportTarget({ type: 'comment', comment: reply })
                        }}
                        onDelete={() => setDeleteTarget({ type: 'comment', comment: reply })}
                        onNavigate={() =>
                          navigate(`/profile/${encodeURIComponent(reply.authorUsername)}`)
                        }
                      />
                    ))}
                  </div>
                )}
              </div>
            )
          })
        )}
      </main>

      {composer && (
        <div className="modal-overlay">
          <div className="modal" role="dialog" aria-modal="true" aria-label="Add comment">
            <h2 className="modal__title">
              {composer.type === 'reply'
                ? `Replying to ${composer.thread.comments[0]?.authorUsername ?? 'comment'}`
                : 'Add a comment'}
            </h2>
            <textarea
              className="text-area"
              rows={4}
              aria-label="Comment text"
              autoFocus
              value={composerText}
              onChange={e => setComposerText(e.target.value)}
            />
            <CharacterCounter value={composerText} max={MAX_COMMENT_LENGTH} />
            <div className="modal__actions">
              <button
                type="button"
                className="modal__cancel"
                onClick={() => {
                  setComposer(null)
                  setComposerText('')
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="modal__confirm"
                disabled={
                  composerText.trim().length === 0 ||
                  !isWithinLimit(composerText, MAX_COMMENT_LENGTH)
                }
                onClick={submitComposer}
              >
                {composer.type === 'reply' ? 'Send' : 'Post'}
              </button>
            </div>
          </div>
        </div>
      )}

      {reportTarget && (
        <div className="modal-overlay">
          <div className="modal" role="dialog" aria-modal="true" aria-label="Report item">
            <h2 className="modal__title">Report Item</h2>
            <input
              className="search-bar"
              type="text"
              placeholder="Reason for reporting..."
              aria-label="Reason for reporting"
              value={reportReason}
              onChange={e => setReportReason(e.target.value)}
            />
            <div className="modal__actions">
              <button
                type="button"
                className="modal__cancel"
                onClick={() => {
                  setReportTarget(null)
                  setReportReason('')
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="modal__confirm"
                disabled={reportReason.trim().length === 0}
                onClick={submitReport}
              >
                Submit Report
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteTarget && (
        <div className="modal-overlay">
          <div className="modal" role="dialog" aria-modal="true" aria-label="Delete item">
            <h2 className="modal__title">
              Delete {deleteTarget.type === 'post' ? 'Post' : 'Comment'}?
            </h2>
            <p className="muted">This can’t be undone.</p>
            <div className="modal__actions">
              <button
                type="button"
                className="modal__cancel"
                onClick={() => setDeleteTarget(null)}
              >
                Cancel
              </button>
              <button type="button" className="modal__confirm" onClick={submitDelete}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function DetailBar({ onBack }: { onBack: () => void }) {
  return (
    <header className="app-bar">
      <button type="button" className="app-bar__back" onClick={onBack}>
        ← Back
      </button>
      <h1 className="app-bar__title">Post</h1>
    </header>
  )
}

interface CommentRowProps {
  comment: CommentView
  isCollapsed: boolean
  onToggleCollapse: () => void
  onToggleLike: () => void
  onReport: () => void
  onDelete: () => void
  onNavigate: () => void
}

function CommentRow({
  comment,
  isCollapsed,
  onToggleCollapse,
  onToggleLike,
  onReport,
  onDelete,
  onNavigate,
}: CommentRowProps) {
  return (
    <div className="comment-row">
      <span className="comment-row__avatar" aria-hidden="true">
        ◍
      </span>
      <div className="comment-row__main">
        {/* The username + time form a header band. The chevron is the real,
            keyboard-accessible collapse control; the surrounding band also
            toggles on click as a mouse convenience (issue #243). The author name
            and chevron are sibling <button>s — never nested inside an interactive
            role — and each stops click propagation so activating one doesn't also
            trigger the band's collapse. */}
        <div className="comment-row__header" onClick={onToggleCollapse}>
          <button
            type="button"
            className="feed-post__author"
            style={{ display: 'inline', padding: 0 }}
            onClick={e => {
              e.stopPropagation()
              onNavigate()
            }}
          >
            <span className="comment-row__author">{comment.authorUsername}</span>
          </button>
          <span className="comment-row__time">{formatRelativeTime(comment.createdTime)}</span>
          <button
            type="button"
            className="comment-row__collapse"
            aria-expanded={!isCollapsed}
            aria-label={isCollapsed ? 'Expand thread' : 'Collapse thread'}
            onClick={e => {
              e.stopPropagation()
              onToggleCollapse()
            }}
          >
            {isCollapsed ? '▸' : '▾'}
          </button>
        </div>
        {/* The comment body sits below the username/time header line. */}
        <p className="comment-row__body">{comment.body}</p>
        <div className="comment-row__info">
          {!comment.isOwn && (
            <button
              type="button"
              className="heart"
              aria-label={comment.isLiked ? 'Unlike comment' : 'Like comment'}
              aria-pressed={comment.isLiked}
              onClick={onToggleLike}
            >
              {comment.isLiked ? '♥' : '♡'}
            </button>
          )}
          <span>{comment.likeCount} likes</span>
          {/* You can't report your own comment — own comments offer Delete. */}
          {comment.isOwn ? (
            <button type="button" className="comment-reply-btn" style={{ padding: 0 }} onClick={onDelete}>
              Delete
            </button>
          ) : (
            <button type="button" className="comment-reply-btn" style={{ padding: 0 }} onClick={onReport}>
              Report
            </button>
          )}
          {comment.isReported && (
            <span className="flag-icon" aria-label="Reported">
              ⚑
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

export default PostDetailPage
