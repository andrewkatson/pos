import { useState, type ReactNode } from 'react'
import { apiClient } from '../api/client'
import type { FeedPost } from '../api/types'

/** Anything can be thrown in JS, so never assume the caught value is an Error:
 * reading `.message` off a string or null would lose the text or throw again.
 * A thrown string carries its own message, so it's used as-is; anything else
 * has no text worth showing and falls back to the caller's wording. */
function messageFrom(err: unknown, fallback: string): string {
  if (err instanceof Error && err.message) return err.message
  if (typeof err === 'string' && err.trim()) return err
  return fallback
}

/** Per-post state the user has changed locally since the list was fetched. */
interface PostOverride {
  isLiked?: boolean
  likeCount?: number
  isSaved?: boolean
  isReported?: boolean
  reportReason?: string | null
}

/** What the UI needs to render one post's controls. */
export interface PostActionState {
  /** The backend rejects liking your own post, so the like control is hidden
   * for it and the menu offers Delete instead of Report. */
  isOwn: boolean
  isLiked: boolean
  likeCount: number
  /** Whether the post is in the user's saved collection (issue #193). */
  isSaved: boolean
  isReported: boolean
  reportReason: string | null
}

type Dialog =
  | { kind: 'menu'; post: FeedPost }
  | { kind: 'report'; post: FeedPost }
  | { kind: 'retract'; post: FeedPost }
  | { kind: 'delete'; post: FeedPost }

interface UsePostActionsOptions {
  /** The signed-in user, used to tell your own posts from everyone else's. */
  currentUsername: string | null
  /** Called after a post is deleted so the caller can drop it from its list. */
  onPostDeleted: (postIdentifier: string) => void
  /** Called after a post is unsaved. The Saved Posts screen uses this to drop
   * the row; feed and profile grids leave it in place (issue #193). */
  onPostUnsaved?: (postIdentifier: string) => void
  /** Surfaces a failed action to the caller's error banner. */
  onError: (message: string) => void
}

/**
 * Like / report / retract-report / delete for posts shown in a list, so the user
 * can act on them without opening each one (issue #267). Shared by the profile
 * grid and the feed, which have different layouts but identical actions.
 *
 * Like/report state comes from the listing endpoints (is_liked / is_reported /
 * report_reason); local overrides layer on top so an action shows immediately
 * without refetching the whole page.
 *
 * Returns `dialogs`, which the caller must render — the confirmation modals are
 * shared by every row rather than duplicated per post.
 */
export function usePostActions({
  currentUsername,
  onPostDeleted,
  onPostUnsaved,
  onError,
}: UsePostActionsOptions): {
  stateFor: (post: FeedPost) => PostActionState
  toggleLike: (post: FeedPost) => void
  toggleSave: (post: FeedPost) => void
  openMenu: (post: FeedPost) => void
  dialogs: ReactNode
} {
  const [overrides, setOverrides] = useState<Record<string, PostOverride>>({})
  const [dialog, setDialog] = useState<Dialog | null>(null)
  const [reportReason, setReportReason] = useState('')

  function stateFor(post: FeedPost): PostActionState {
    const override = overrides[post.post_identifier] ?? {}
    return {
      isOwn: post.author_username === currentUsername,
      isLiked: override.isLiked ?? post.is_liked ?? false,
      likeCount: override.likeCount ?? post.post_likes ?? 0,
      isSaved: override.isSaved ?? post.is_saved ?? false,
      isReported: override.isReported ?? post.is_reported ?? false,
      // Retracting sets the override to null, which ?? would treat as absent and
      // fall back to the stale server reason — so test for the key instead.
      reportReason:
        'reportReason' in override
          ? (override.reportReason ?? null)
          : (post.report_reason ?? null),
    }
  }

  function setOverride(postIdentifier: string, patch: PostOverride) {
    setOverrides(prev => ({
      ...prev,
      [postIdentifier]: { ...prev[postIdentifier], ...patch },
    }))
  }

  async function toggleLikeAsync(post: FeedPost) {
    const { isOwn, isLiked, likeCount } = stateFor(post)
    // The control isn't rendered for your own post; guard anyway so a stray call
    // can't desync the count against a request the backend will reject.
    if (isOwn) return
    const liking = !isLiked
    setOverride(post.post_identifier, {
      isLiked: liking,
      likeCount: liking ? likeCount + 1 : Math.max(0, likeCount - 1),
    })
    try {
      if (liking) await apiClient.likePost(post.post_identifier)
      else await apiClient.unlikePost(post.post_identifier)
    } catch (err) {
      // Revert to the pre-click values.
      setOverride(post.post_identifier, { isLiked, likeCount })
      onError(messageFrom(err, 'Action failed.'))
    }
  }

  async function toggleSaveAsync(post: FeedPost) {
    const { isSaved } = stateFor(post)
    const saving = !isSaved
    setOverride(post.post_identifier, { isSaved: saving })
    try {
      if (saving) await apiClient.savePost(post.post_identifier)
      else await apiClient.unsavePost(post.post_identifier)
      // Only after the server confirms the unsave does the caller drop the row,
      // so a failed request leaves the post on the Saved screen to retry.
      if (!saving) onPostUnsaved?.(post.post_identifier)
    } catch (err) {
      setOverride(post.post_identifier, { isSaved })
      onError(messageFrom(err, saving ? 'Failed to save.' : 'Failed to unsave.'))
    }
  }

  async function submitReport() {
    const reason = reportReason.trim()
    if (!reason || dialog?.kind !== 'report') return
    const { post } = dialog
    setDialog(null)
    setReportReason('')
    try {
      await apiClient.reportPost(post.post_identifier, reason)
      setOverride(post.post_identifier, { isReported: true, reportReason: reason })
    } catch (err) {
      onError(messageFrom(err, 'Failed to report.'))
    }
  }

  async function submitRetract() {
    if (dialog?.kind !== 'retract') return
    const { post } = dialog
    setDialog(null)
    try {
      await apiClient.retractReportPost(post.post_identifier)
      setOverride(post.post_identifier, { isReported: false, reportReason: null })
    } catch (err) {
      onError(messageFrom(err, 'Failed to retract report.'))
    }
  }

  async function submitDelete() {
    if (dialog?.kind !== 'delete') return
    const { post } = dialog
    setDialog(null)
    try {
      await apiClient.deletePost(post.post_identifier)
      // Drop any override for the deleted post: the row is gone from the
      // caller's list, so the entry would just accumulate for the life of the
      // session as the user pages through and acts on more posts.
      setOverrides(prev => {
        if (!(post.post_identifier in prev)) return prev
        const { [post.post_identifier]: _removed, ...rest } = prev
        return rest
      })
      onPostDeleted(post.post_identifier)
    } catch (err) {
      onError(messageFrom(err, 'Failed to delete.'))
    }
  }

  const dialogs = (
    <>
      {dialog?.kind === 'menu' && (
        <div className="modal-overlay">
          <div className="modal" role="dialog" aria-modal="true" aria-label="Post options">
            <h2 className="modal__title">Post options</h2>
            <div className="modal__actions">
              <button type="button" className="modal__cancel" onClick={() => setDialog(null)}>
                Cancel
              </button>
              {stateFor(dialog.post).isOwn ? (
                <button
                  type="button"
                  className="modal__confirm"
                  onClick={() => setDialog({ kind: 'delete', post: dialog.post })}
                >
                  Delete
                </button>
              ) : stateFor(dialog.post).isReported ? (
                <button
                  type="button"
                  className="modal__confirm"
                  onClick={() => setDialog({ kind: 'retract', post: dialog.post })}
                >
                  Retract Report
                </button>
              ) : (
                <button
                  type="button"
                  className="modal__confirm"
                  onClick={() => {
                    setReportReason('')
                    setDialog({ kind: 'report', post: dialog.post })
                  }}
                >
                  Report
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {dialog?.kind === 'report' && (
        <div className="modal-overlay">
          <div className="modal" role="dialog" aria-modal="true" aria-label="Report post">
            <h2 className="modal__title">Report Post</h2>
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
                  setDialog(null)
                  setReportReason('')
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="modal__confirm"
                disabled={reportReason.trim().length === 0}
                onClick={() => void submitReport()}
              >
                Submit Report
              </button>
            </div>
          </div>
        </div>
      )}

      {dialog?.kind === 'retract' && (
        <div className="modal-overlay">
          <div className="modal" role="dialog" aria-modal="true" aria-label="Retract report">
            <h2 className="modal__title">Retract Report?</h2>
            <p className="muted">
              You reported this post with the reason below. Retracting removes your report.
            </p>
            <input
              className="search-bar"
              type="text"
              readOnly
              aria-label="Your report reason"
              value={stateFor(dialog.post).reportReason ?? ''}
            />
            <div className="modal__actions">
              <button type="button" className="modal__cancel" onClick={() => setDialog(null)}>
                Cancel
              </button>
              <button type="button" className="modal__confirm" onClick={() => void submitRetract()}>
                Retract Report
              </button>
            </div>
          </div>
        </div>
      )}

      {dialog?.kind === 'delete' && (
        <div className="modal-overlay">
          <div className="modal" role="dialog" aria-modal="true" aria-label="Delete post">
            <h2 className="modal__title">Delete Post?</h2>
            <p className="muted">This can’t be undone.</p>
            <div className="modal__actions">
              <button type="button" className="modal__cancel" onClick={() => setDialog(null)}>
                Cancel
              </button>
              <button type="button" className="modal__confirm" onClick={() => void submitDelete()}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )

  return {
    stateFor,
    toggleLike: post => void toggleLikeAsync(post),
    toggleSave: post => void toggleSaveAsync(post),
    openMenu: post => setDialog({ kind: 'menu', post }),
    dialogs,
  }
}

