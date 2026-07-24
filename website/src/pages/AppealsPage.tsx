import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { ApiError } from '../api/client'
import type { AppealTargetType, HiddenComment, HiddenPost, MyAppeal } from '../api/types'
import CaptionTile from '../components/CaptionTile'
import './MainApp.css'

/**
 * "Hidden content & appeals": the signed-in user's own hidden posts and
 * comments, each appealable once, plus the status of appeals they have filed.
 * Mirrors the iOS/Android appeals views. Ban appeals are not here — those go
 * through the suspension email (an outright-banned user has no session).
 */
function AppealsPage() {
  if (!apiClient.isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return <AppealsView />
}

const REASON_LABEL: Record<string, string> = {
  classifier: 'Flagged by automated review',
  reports: 'Hidden after user reports',
  '': 'Hidden',
}

function hiddenReasonLabel(reason: string): string {
  return REASON_LABEL[reason] ?? 'Hidden'
}

interface AppealTarget {
  type: AppealTargetType
  id: string
  preview: string
}

function AppealsView() {
  const navigate = useNavigate()
  const isMounted = useRef(true)
  useEffect(() => {
    isMounted.current = true
    return () => {
      isMounted.current = false
    }
  }, [])

  const [hiddenPosts, setHiddenPosts] = useState<HiddenPost[]>([])
  const [hiddenComments, setHiddenComments] = useState<HiddenComment[]>([])
  const [appeals, setAppeals] = useState<MyAppeal[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // The item currently being appealed (drives the reason modal).
  const [target, setTarget] = useState<AppealTarget | null>(null)
  const [reason, setReason] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const load = useCallback(async () => {
    try {
      if (isMounted.current) setErrorMessage(null) // drop any stale error before reloading
      const [posts, comments, mine] = await Promise.all([
        apiClient.getHiddenPosts(0),
        apiClient.getHiddenComments(0),
        apiClient.getMyAppeals(0),
      ])
      if (!isMounted.current) return
      setHiddenPosts(posts)
      setHiddenComments(comments)
      setAppeals(mine)
    } catch (err) {
      if (isMounted.current) setErrorMessage((err as ApiError).message ?? 'Failed to load.')
    } finally {
      if (isMounted.current) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void Promise.resolve().then(load)
  }, [load])

  function openAppeal(t: AppealTarget) {
    setTarget(t)
    setReason('')
    setErrorMessage(null)
  }

  async function submitAppeal() {
    if (!target || reason.trim().length === 0) return
    setIsSubmitting(true)
    setErrorMessage(null)
    try {
      await apiClient.submitAppeal({
        target_type: target.type,
        target_identifier: target.id,
        reason: reason.trim(),
      })
      setTarget(null)
      setIsLoading(true)
      await load()
    } catch (err) {
      setErrorMessage((err as ApiError).message ?? 'Failed to submit appeal.')
    } finally {
      if (isMounted.current) setIsSubmitting(false)
    }
  }

  const nothingHidden = hiddenPosts.length === 0 && hiddenComments.length === 0
  const noAppeals = appeals.length === 0

  return (
    <div className="app-shell">
      <header className="app-bar">
        <button type="button" className="app-bar__back" onClick={() => navigate(-1)}>
          ← Back
        </button>
        <h1 className="app-bar__title">Hidden Content &amp; Appeals</h1>
      </header>

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

        {isLoading ? (
          <div className="center-spinner">
            <span className="spinner" />
          </div>
        ) : (
          <>
            <section className="settings-group">
              <span className="settings-group__header">Hidden Content</span>
              {nothingHidden && <p className="muted">None of your content is hidden.</p>}

              {hiddenPosts.map(post => (
                <div key={post.post_identifier} className="appeal-item">
                  {post.image_url === null ? (
                    <CaptionTile
                      caption={post.caption}
                      captionFont={post.caption_font}
                      backgroundColor={post.background_color}
                      variant="thumb"
                    />
                  ) : (
                    <img className="appeal-item__thumb" src={post.image_url} alt={post.caption} />
                  )}
                  <div className="appeal-item__body">
                    <p className="appeal-item__text">{post.caption}</p>
                    <p className="muted">{hiddenReasonLabel(post.hidden_reason)}</p>
                  </div>
                  <AppealAction
                    hasAppeal={post.has_appeal}
                    label={`Appeal post`}
                    onAppeal={() =>
                      openAppeal({ type: 'post', id: post.post_identifier, preview: post.caption })
                    }
                  />
                </div>
              ))}

              {hiddenComments.map(comment => (
                <div key={comment.comment_identifier} className="appeal-item">
                  <div className="appeal-item__body">
                    <p className="appeal-item__text">{comment.body}</p>
                    <p className="muted">{hiddenReasonLabel(comment.hidden_reason)}</p>
                  </div>
                  <AppealAction
                    hasAppeal={comment.has_appeal}
                    label={`Appeal comment`}
                    onAppeal={() =>
                      openAppeal({
                        type: 'comment',
                        id: comment.comment_identifier,
                        preview: comment.body,
                      })
                    }
                  />
                </div>
              ))}
            </section>

            <section className="settings-group">
              <span className="settings-group__header">Your Appeals</span>
              {noAppeals && <p className="muted">You haven't filed any appeals.</p>}
              {appeals.map(appeal => (
                <div key={appeal.appeal_identifier} className="appeal-item">
                  <div className="appeal-item__body">
                    <p className="appeal-item__text">
                      {appeal.content_snapshot ?? appeal.target_type ?? 'Appeal'}
                    </p>
                    <p className="muted">Reason: {appeal.reason}</p>
                    {appeal.resolution_note && (
                      <p className="muted">Note: {appeal.resolution_note}</p>
                    )}
                  </div>
                  <span className={`appeal-status appeal-status--${appeal.status}`}>
                    {appeal.status}
                  </span>
                </div>
              ))}
            </section>
          </>
        )}
      </main>

      {target && (
        <div className="modal-overlay">
          <div className="modal" role="dialog" aria-modal="true" aria-label="Appeal">
            <h2 className="modal__title">Appeal this {target.type}</h2>
            <p className="modal__body">{target.preview}</p>
            <textarea
              className="text-area"
              rows={4}
              aria-label="Appeal reason"
              placeholder="Why should this be restored?"
              value={reason}
              onChange={e => setReason(e.target.value)}
              disabled={isSubmitting}
            />
            <div className="modal__actions">
              <button
                type="button"
                className="modal__cancel"
                onClick={() => setTarget(null)}
                disabled={isSubmitting}
              >
                Cancel
              </button>
              <button
                type="button"
                className="modal__confirm"
                disabled={reason.trim().length === 0 || isSubmitting}
                onClick={submitAppeal}
              >
                Submit Appeal
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

interface AppealActionProps {
  hasAppeal: boolean
  label: string
  onAppeal: () => void
}

function AppealAction({ hasAppeal, label, onAppeal }: AppealActionProps) {
  if (hasAppeal) {
    return <span className="appeal-status appeal-status--pending">Appealed</span>
  }
  return (
    <button type="button" className="btn btn-primary appeal-item__action" onClick={onAppeal}>
      {label}
    </button>
  )
}

export default AppealsPage
