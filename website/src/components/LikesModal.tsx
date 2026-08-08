import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { apiClient } from '../api/client'
import type { UserSearchResult } from '../api/types'
import { profilePathFor } from '../utils/profilePath'
import Avatar from './Avatar'
import Modal from './Modal'

/** What the dialog is listing the likers of. Identifiers rather than a fetch
 * closure, so the loader can be memoized on primitives and the list isn't
 * refetched on every render of the caller. */
export type LikesTarget =
  | { kind: 'post'; postIdentifier: string }
  | {
      kind: 'comment'
      postIdentifier: string
      commentThreadIdentifier: string
      commentIdentifier: string
    }

interface LikesModalProps {
  target: LikesTarget
  onClose: () => void
}

/**
 * "Who liked this" (issue #478): the scrollable, batched list of accounts behind
 * a post's or comment's like count, opened by tapping that count.
 *
 * Only ever shown for the signed-in user's own content — the backend answers for
 * nobody else's — so callers make the count tappable only on their own posts and
 * comments.
 *
 * Likers arrive a batch at a time rather than all at once, so a post with
 * thousands of likes costs one screenful of rows to open. The list scrolls
 * inside the dialog and "Load more" appends the next batch, mirroring the feed's
 * pagination. Each row taps through to that user's profile.
 *
 * Mirrors the iOS LikesView and the Android LikesDialog.
 */
function LikesModal({ target, onClose }: LikesModalProps) {
  const navigate = useNavigate()

  const isMounted = useRef(true)
  useEffect(() => {
    isMounted.current = true
    return () => {
      isMounted.current = false
    }
  }, [])

  const [users, setUsers] = useState<UserSearchResult[]>([])
  const [page, setPage] = useState(0)
  const [canLoadMore, setCanLoadMore] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Pulled apart into primitives before memoizing: the loader must depend on the
  // identifiers, not on the `target` object, or a caller that rebuilds the
  // literal each render would restart the fetch on every render.
  const { kind, postIdentifier } = target
  const threadIdentifier = target.kind === 'comment' ? target.commentThreadIdentifier : ''
  const commentIdentifier = target.kind === 'comment' ? target.commentIdentifier : ''

  const fetcher = useCallback(
    (batch: number) =>
      kind === 'post'
        ? apiClient.getPostLikers(postIdentifier, batch)
        : apiClient.getCommentLikers(postIdentifier, threadIdentifier, commentIdentifier, batch),
    [kind, postIdentifier, threadIdentifier, commentIdentifier],
  )

  const load = useCallback(
    async (pageToLoad: number, replace: boolean) => {
      // Owned here rather than by the caller so every entry point — the mount
      // effect, a target change, "Load more" — shows the spinner and drops the
      // previous error. A replace also clears the list up front, so a switch to
      // a different post can't leave the old post's likers on screen while the
      // new batch is in flight. Matches the iOS/Android view models.
      setIsLoading(true)
      setErrorMessage(null)
      if (replace) {
        setUsers([])
        setCanLoadMore(false)
        setPage(0)
      }
      try {
        const batch = await fetcher(pageToLoad)
        if (!isMounted.current) return
        if (replace) {
          setUsers(batch)
          setCanLoadMore(batch.length > 0)
          setPage(batch.length > 0 ? 1 : 0)
        } else if (batch.length === 0) {
          setCanLoadMore(false)
        } else {
          setUsers(prev => [...prev, ...batch])
          setPage(prev => prev + 1)
        }
      } catch (err) {
        if (!isMounted.current) return
        // A failed page leaves what is already listed in place and stops paging,
        // so the dialog degrades to "here is what we have" rather than emptying.
        setCanLoadMore(false)
        setErrorMessage(err instanceof Error && err.message ? err.message : 'Failed to load likes.')
      } finally {
        if (isMounted.current) setIsLoading(false)
      }
    },
    [fetcher],
  )

  // Deferred to a microtask so the fetch's setState calls don't run
  // synchronously inside the effect, matching the feed's loader.
  useEffect(() => {
    void Promise.resolve().then(() => load(0, true))
  }, [load])

  return (
    <Modal title={kind === 'post' ? 'Likes' : 'Comment likes'}>
      {errorMessage && (
        <div className="auth-error" role="alert">
          <p>{errorMessage}</p>
        </div>
      )}

      {isLoading && users.length === 0 ? (
        <div className="center-spinner">
          <span className="spinner" />
        </div>
      ) : users.length === 0 ? (
        // Only when the list really came back empty — a failed load already
        // says why above, and "no one has liked this" would contradict it.
        errorMessage ? null : <p className="muted">No one has liked this yet.</p>
      ) : (
        <div className="likes-list user-list">
          {users.map(user => (
            <button
              key={user.username}
              type="button"
              className="user-list__item"
              onClick={() => {
                onClose()
                navigate(profilePathFor(user.username))
              }}
            >
              <Avatar
                src={user.author_profile_image_url}
                originalSrc={user.author_profile_image_original_url}
                username={user.username}
                size="sm"
              />
              <span className="user-list__name">{user.username}</span>
              {user.identity_is_verified && (
                <span className="verified-badge" aria-label="Verified">
                  ✓
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {canLoadMore && !isLoading && users.length > 0 && (
        <button type="button" className="load-more" onClick={() => void load(page, false)}>
          Load more
        </button>
      )}

      <div className="modal__actions">
        <button type="button" className="modal__cancel" onClick={onClose}>
          Close
        </button>
      </div>
    </Modal>
  )
}

export default LikesModal
